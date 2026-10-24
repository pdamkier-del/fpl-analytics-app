"""Export public predictions with a real capture clock, never backdate them.

This is publication evidence only. It does not change a forecast, model,
manager state, or any PM/TS calculation.
"""
import argparse,gzip,hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path


def utc(value):
    result=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('A timezone is required')
    return result.astimezone(timezone.utc)


def build_records(forecast,mm,*,recorded_at,catalogue=()):
    now=utc(recorded_at);asof=utc(forecast['data_asof']);deadline=utc(forecast['origin_deadline'])
    by={(r['player_id'],r['fixture_id']):r for r in mm['players']}
    codes={r['id']:r.get('code')for r in catalogue};rows=[];seen=set()
    for player in forecast['players']:
        for week in player['weeks']:
            for f in week['fixtures']:
                key=(player['player_uuid'],f['fixture_uuid'])
                if key in seen:raise ValueError('Duplicate player/fixture prediction')
                seen.add(key);m=by[key]
                rows.append(dict(player_id=player['id'],player_uuid=player['player_uuid'],
                    fpl_code=codes.get(player['id']),team_id=player['team_id'],position=player['position'],
                    gw=week['gw'],fixture_uuid=f['fixture_uuid'],kickoff=f['kickoff'],
                    p_start=f['p_start'],p_play=m['p_play'],p60=f['p_60_plus'],p90=f['p_90'],
                    expected_minutes=f['xmins'],xp=f['xpts'],point_components=f['components'],
                    eligible_for_pre_match_validation=asof<=now<deadline and now<utc(f['kickoff'])))
    manifest=dict(schema='B-prospective-player-ledger-v1',season=forecast['season'],
        forecast_sha256=forecast['forecast_sha256'],data_asof=forecast['data_asof'],
        recorded_at=now.isoformat(),origin_deadline=forecast['origin_deadline'],
        records=len(rows),eligible_records=sum(r['eligible_for_pre_match_validation']for r in rows),
        forecast_code_sha256=forecast.get('code_sha256',{}),
        forecast_input_sha256=forecast.get('input_sha256',{}),
        missing_stable_player_codes=sum(r['fpl_code'] is None for r in rows),
        whole_model_certification=False,production_changed=False,private_user_state_used=False,
        limitation='Recording a prediction does not certify its quality. Later captures are not retrospectively pre-deadline predictions.')
    return manifest,rows


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--capture',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    load=lambda p:json.loads((a.capture/p).read_text())
    f=load('current/forecast.json');mm=load('current/mm.json')
    from fpl_v1_1_model.forecast_snapshot import require_snapshot
    require_snapshot(f)
    index=load('current/index.json')
    if index['forecast_sha256']!=f['forecast_sha256']:
        raise ValueError('Prospective ledger forecast/index mismatch')
    for name,key in [('forecast.json','forecast_file_sha256'),('mm.json','mm_file_sha256'),('existing-app-data.json','existing_app_data_sha256')]:
        if hashlib.sha256((a.capture/'current'/name).read_bytes()).hexdigest()!=index[key]:
            raise ValueError('Prospective ledger source checksum mismatch: '+name)
    docs=load('current/existing-app-data.json');assert docs['forecast_sha256']==f['forecast_sha256']
    manifest,rows=build_records(f,mm,recorded_at=datetime.now(timezone.utc).isoformat(),
        catalogue=docs['documents']['current-players.json']['players'])
    manifest['publication_run']=os.environ.get('GITHUB_RUN_ID')
    manifest['archiver_code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    raw=('\n'.join(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False)for r in rows)+'\n').encode()
    compressed=gzip.compress(raw,mtime=0);a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'prospective-ledger.jsonl.gz').write_bytes(compressed)
    manifest.update(file='prospective-ledger.jsonl.gz',sha256=hashlib.sha256(compressed).hexdigest())
    (a.out/'prospective-ledger-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:manifest[k]for k in ['forecast_sha256','recorded_at','records','eligible_records','private_user_state_used']}))


if __name__=='__main__':main()
