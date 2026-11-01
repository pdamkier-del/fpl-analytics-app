"""After a verified news publication, request one needed B refresh.

Only the existing preview workflow can be dispatched. No manager data is read.
The numerical model and all freshness/availability gates remain unchanged.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess

REPO = 'pdamkier-del/fpl-analytics-app'
WORKFLOW = 'mm-current-preview-publication.yml'
ACTIVE = {'queued', 'in_progress', 'waiting', 'pending', 'requested'}


def identity(player):
    return (player.get('team'), player.get('position'),
            player.get('price_tenths', round(player.get('price', 0) * 10)),
            player.get('status'), player.get('news') or '', player.get('news_added'),
            player.get('chance_of_playing_next_round'), player.get('chance_of_playing_this_round'))


def checked(path, digest):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('Unverified preview file: ' + path.name)
    return json.loads(raw)


def refresh_reason(site, now):
    from dashboard_news_publication import checked as check_news
    base = Path(site) / 'mm-preview'
    news, observed = check_news((base / 'news/availability.json').read_bytes(), now)
    if now - observed > timedelta(hours=1):
        raise ValueError('Fresh official news is required before dispatch')
    index = json.loads((base / 'current/index.json').read_text())
    if index.get('model') != 'B-MM-PM-TS-v1':
        raise ValueError('Only the unified B preview may be refreshed')
    data = checked(base / 'current/existing-app-data.json', index['existing_app_data_sha256'])
    forecast = checked(base / 'current/forecast.json', index['forecast_file_sha256'])
    if data['forecast_sha256'] != index['forecast_sha256'] or forecast['forecast_sha256'] != index['forecast_sha256']:
        raise ValueError('Preview snapshot identities differ')
    old = {p['id']: p for p in data['documents']['current-players.json']['players']}
    fresh = {p['id']: p for p in news['players']}
    if forecast['gws'][0] != news['next_gw']:
        return 'new_gameweek'
    if old.keys() != fresh.keys() or any(identity(old[pid]) != identity(fresh[pid]) for pid in fresh):
        return 'official_player_information_changed'
    if now - datetime.fromisoformat(forecast['data_asof'].replace('Z', '+00:00')) > timedelta(hours=6):
        return 'model_source_older_than_six_hours'
    return None


def maybe_request(reason, runs, dispatch, now):
    if not reason:
        return dict(requested=False, reason='already_current')
    if any(run['status'] in ACTIVE for run in runs):
        return dict(requested=False, reason='refresh_already_in_flight', trigger=reason)
    latest = max((datetime.fromisoformat((r.get('run_started_at') or r['created_at']).replace('Z', '+00:00')) for r in runs), default=None)
    if latest and now - latest < timedelta(minutes=30):
        return dict(requested=False, reason='recent_attempt_wait', trigger=reason)
    dispatch()
    return dict(requested=True, reason=reason, workflow=WORKFLOW, ref='main')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', type=Path, default=Path('.mm-preview-site'))
    ap.add_argument('--out', type=Path, default=Path('work/news-model-refresh.json'))
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    reason = refresh_reason(args.site, now)
    prefix = f'repos/{REPO}/actions/workflows/{WORKFLOW}'
    runs = json.loads(subprocess.check_output(['gh', 'api', prefix + '/runs?per_page=30']))['workflow_runs'] if reason else []
    def dispatch():
        subprocess.run(['gh', 'api', prefix + '/dispatches', '--method', 'POST', '--input', '-'],
                       input=json.dumps({'ref': 'main'}).encode(), check=True)
    result = maybe_request(reason, runs, dispatch, now)
    result.update(checked_at=now.isoformat(), production_changed=False, manager_data_read=False)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
