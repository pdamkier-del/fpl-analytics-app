"""Research-only availability archive audit. No imports from forecast/model code.

Online capture pins Git objects and verifies conservative server-run timestamps.
Offline rebuild: --rebuild <existing-output> --out <new-output> (no network/Core).
Output directories are immutable; never replace an earlier ledger.
"""
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import re
import sqlite3
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PIN = '17e703acd4f744931afa9d1d90a2998cfb104286'
ARCHIVE = 'Randdalf/fplcache'
API = 'https://api.github.com/repos/' + ARCHIVE
UTC = dt.timezone.utc

def timestamp(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(UTC)

def iso(t):
    return t.isoformat().replace('+00:00', 'Z')

def sha(b):
    return hashlib.sha256(b).hexdigest()

def get(url, cache):
    path = cache / sha(url.encode())
    if path.exists():
        return path.read_bytes()
    headers = {'User-Agent': 'FPL-availability-research', 'Accept': 'application/vnd.github+json'}
    if url.startswith('https://api.github.com/') and os.environ.get('GH_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
    for attempt in range(3):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=50).read()
            path.write_bytes(raw)
            return raw
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 + attempt)

def getj(url, cache):
    return json.loads(get(url, cache))

def normalized(status, chance=None, previous=None):
    # Chance is used only when its event scope can be established from the payload.
    if status == 'a':
        return 'RETURNED_AVAILABLE' if previous in {'d', 'i', 's', 'u'} else 'AVAILABLE'
    if status == 's':
        return 'SUSPENDED'
    if status in {'i', 'u'}:
        return 'OUT'
    if status == 'd':
        return 'MAJOR_DOUBT' if chance is not None and chance <= 25 else 'DOUBT'
    return 'UNKNOWN'

def certified_time(nominal, commit_at, parent, runs):
    valid = []
    for run in runs:
        if (run.get('name') == 'cache' and run.get('head_sha') == parent
                and run.get('status') == 'completed' and run.get('conclusion') == 'success'
                and timestamp(run['created_at']) < nominal + dt.timedelta(minutes=1) and nominal <= timestamp(run['updated_at'])
                and timestamp(run['created_at']) <= commit_at <= timestamp(run['updated_at'])):
            valid.append(run)
    if not valid:
        return max(nominal, commit_at), False, None
    run = min(valid, key=lambda x: x['updated_at'])
    return max(nominal, commit_at, timestamp(run['updated_at'])), True, run

def write_json(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n')

def write_gz(p, rows):
    raw = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows).encode()
    p.write_bytes(gzip.compress(raw, mtime=0))

def read_gz(p):
    return [json.loads(s) for s in gzip.decompress(p.read_bytes()).splitlines()]

def known_identities(db):
    con = sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)
    ids, codes = {}, {}
    for uuid, external in con.execute("SELECT DISTINCT player_uuid,external_id FROM player_id_mapping WHERE id_namespace='fpl_element' AND season='2025-26'"):
        ids.setdefault(str(external), set()).add(uuid)
    for uuid, external in con.execute("SELECT DISTINCT player_uuid,external_id FROM player_id_mapping WHERE id_namespace='fpl_code'"):
        codes.setdefault(uuid, set()).add(str(external))
    con.close()
    return ids, codes

def collect(db, cache):
    existing = ROOT / 'analysis/results/joint-deadline-snapshots-v1'
    manifest = json.loads((existing / 'manifest.json').read_text())
    last = next(r for r in manifest['sources'] if r['gw'] == 38)
    pieces = []
    for p in last['parts']:
        raw = (existing / p['path']).read_bytes()
        assert sha(raw) == p['sha256']
        pieces.append(raw)
    raw = b''.join(pieces)
    assert sha(raw) == last['sha256']
    deadlines = [{'gw': e['id'], 'cutoff': e['deadline_time']} for e in json.loads(lzma.decompress(raw))['events']]
    candidates = []
    trees = {2025: '44e26d825d98da8f171d2d0d07d20accfc2baf6c', 2026: '96cc8b545063c615db5da224637e6b10a1fa06d9'}
    for year, tree in trees.items():
        j = getj(API + '/git/trees/' + tree + '?recursive=1', cache)
        assert not j.get('truncated')
        for entry in j['tree']:
            m = re.fullmatch(r'(\d+)/(\d+)/(\d{2})(\d{2})\.json\.xz', entry['path'])
            if m:
                mo, day, hour, minute = map(int, m.groups())
                candidates.append({'path': f"cache/{year}/{entry['path']}", 'sha': entry['sha'], 'nominal': iso(dt.datetime(year, mo, day, hour, minute, tzinfo=UTC))})
    candidates.sort(key=lambda x: x['nominal'])
    ids, codes = known_identities(db)
    observations, sources = [], []
    for d in deadlines:
        cutoff = timestamp(d['cutoff'])
        pre = [r for r in candidates if timestamp(r['nominal']) < cutoff]
        post = [r for r in candidates if timestamp(r['nominal']) >= cutoff]
        choices = [('nearest_pre_clock', pre[-1]), ('nearest_post_clock', post[0])]
        for label, c in choices:
            url = API + '/commits?sha=' + PIN + '&path=' + c['path'] + '&per_page=1'
            commits = getj(url, cache)
            assert commits, c['path']
            commit = commits[0]
            parent = commit['parents'][0]['sha']
            run_url = API + '/actions/runs?head_sha=' + parent + '&per_page=100'
            run_result = getj(run_url, cache)
            # Refuse a truncated timestamp search rather than quietly guessing.
            assert run_result['total_count'] <= 100
            clock_time = max(timestamp(c['nominal']), timestamp(commit['commit']['committer']['date']))
            effective, verified, run = certified_time(timestamp(c['nominal']), timestamp(commit['commit']['committer']['date']), parent, run_result['workflow_runs'])
            job = None
            jobs_url = API + '/actions/runs/' + str(run['id']) + '/jobs?per_page=100' if run else None
            if run:
                jobs = getj(jobs_url, cache)
                assert jobs['total_count'] <= 100
                good = [j for j in jobs['jobs'] if j.get('name') == 'cache' and j.get('conclusion') == 'success'
                        and j.get('completed_at') and timestamp(j['started_at']) <= timestamp(commit['commit']['committer']['date']) <= timestamp(j['completed_at'])]
                if good:
                    job = min(good, key=lambda j: j['completed_at'])
                    effective = max(clock_time, timestamp(job['completed_at']))
            # Verify the historical fetch/push pipeline, not just today's archive workflow.
            pipeline = {}
            pipeline_ok = True
            for path in ['cache.py', '.github/workflows/cache.yml']:
                prefix = 'https://raw.githubusercontent.com/' + ARCHIVE + '/'
                historical = get(prefix + parent + '/' + path, cache)
                pinned = get(prefix + PIN + '/' + path, cache)
                pipeline[path] = dict(url=prefix + parent + '/' + path, sha256=sha(historical), identical_to_pinned=historical == pinned)
                pipeline_ok = pipeline_ok and historical == pinned
            assert b'https://fantasy.premierleague.com/api/bootstrap-static/' in get('https://raw.githubusercontent.com/'+ARCHIVE+'/'+PIN+'/cache.py', cache)
            assert b'git push' in get('https://raw.githubusercontent.com/'+ARCHIVE+'/'+PIN+'/.github/workflows/cache.yml', cache)
            verified = verified and pipeline_ok
            source_url = 'https://raw.githubusercontent.com/' + ARCHIVE + '/' + commit['sha'] + '/' + c['path']
            raw = get(source_url, cache)
            assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == c['sha']
            payload = json.loads(lzma.decompress(raw))
            ev = next(e for e in payload['events'] if e['id'] == d['gw'])
            deadline_matches = timestamp(ev['deadline_time']) == cutoff
            teams = {t['id']: t for t in payload['teams']}
            current = next((e['id'] for e in payload['events'] if e.get('is_current')), None)
            nextev = next((e['id'] for e in payload['events'] if e.get('is_next')), None)
            source_id = commit['sha'] + ':' + c['path']
            src = dict(c, source_id=source_id, source_url=source_url, source_commit=commit['sha'],
                       commit_at=commit['commit']['committer']['date'], effective_at=iso(effective), timing_verified=verified,
                       run_id=run['id'] if run else None, run_updated_at=run['updated_at'] if run else None,
                       job_id=job['id'] if job else None, job_completed_at=job['completed_at'] if job else None,
                       jobs_metadata_url=jobs_url, parent_commit=parent, pipeline=pipeline, pipeline_verified=pipeline_ok,
                       archive_clock_effective_at=iso(clock_time),
                       run_created_at=run['created_at'] if run else None, commit_metadata_url=url, run_metadata_url=run_url,
                       raw_sha256=sha(raw), audit_gw=d['gw'], cutoff=d['cutoff'], selection=label,
                       deadline_matches=deadline_matches, official_deadline=ev['deadline_time'])
            sources.append(src)
            for e in payload['elements']:
                uuids = ids.get(str(e['id']), set())
                uuid = next(iter(uuids)) if len(uuids) == 1 else None
                identity = 'mapped' if uuid and str(e['code']) in codes.get(uuid, set()) else 'ambiguous' if len(uuids) > 1 else 'unresolved'
                if identity != 'mapped':
                    uuid = None
                scoped_chance = e.get('chance_of_playing_this_round') if current == d['gw'] else e.get('chance_of_playing_next_round') if nextev == d['gw'] else None
                news_added = e.get('news_added')
                future_news = bool(news_added and timestamp(news_added) > effective)
                observations.append(dict(season='2025-26', gw=d['gw'], cutoff=d['cutoff'], player_uuid=uuid,
                    fpl_element=e['id'], fpl_code=e['code'], player_name=e['first_name'] + ' ' + e['second_name'],
                    team=teams[e['team']]['name'], team_id=e['team'], observed_at=c['nominal'], effective_at=iso(effective),
                    source='official_fpl_bootstrap_via_randdalf_archive', source_id=source_id, source_url=source_url,
                    source_commit=commit['sha'], timing_verified=verified, archive_clock_effective_at=iso(clock_time),
                    timestamp_basis=('github_successful_cache_job_completion' if job else 'github_successful_cache_run_updated_upper_bound') if verified else 'archive_clock_only',
                    raw_status=e.get('status'), raw_news=e.get('news'), news_added=news_added,
                    chance_this_round=e.get('chance_of_playing_this_round'), chance_next_round=e.get('chance_of_playing_next_round'),
                    payload_current_event=current, payload_next_event=nextev, scoped_chance=scoped_chance,
                    normalized_availability_state=normalized(e.get('status'), scoped_chance), identity_status=identity,
                    selection=label, deadline_matches=deadline_matches, future_news_timestamp=future_news,
                    strict_eligible=verified and effective < cutoff and deadline_matches and not future_news,
                    conditional_clock_eligible=clock_time < cutoff and deadline_matches and (not news_added or timestamp(news_added) <= clock_time)))
            print('GW', d['gw'], label, 'verified', verified, 'players', len(payload['elements']), flush=True)
    return observations, sources, deadlines

def project(observations, deadlines, strict):
    # Only audited snapshots, not a claim of observing every update between captures.
    pool = {}
    for original in observations:
        r = dict(original)
        if not strict:
            r['effective_at'] = r['archive_clock_effective_at']
            r['timestamp_basis'] = 'archive_clock_only'
            r['future_news_timestamp'] = bool(r['news_added'] and timestamp(r['news_added']) > timestamp(r['effective_at']))
        if r['deadline_matches'] and not r['future_news_timestamp'] and (r['timing_verified'] or not strict):
            pool[(r['source_id'], r['fpl_element'])] = r
    pool = list(pool.values())
    result, coverage, previous = [], [], {}
    for d in deadlines:
        cutoff = timestamp(d['cutoff'])
        eligible = [r for r in pool if timestamp(r['effective_at']) < cutoff]
        # A complete bootstrap is the cohort; absence never implies an injury status.
        newest = max((r['effective_at'] for r in eligible), default=None)
        cohort = [r for r in eligible if r['effective_at'] == newest] if newest else []
        out = []
        for r in cohort:
            row = dict(r, gw=d['gw'], cutoff=d['cutoff'], observation_audit_gw=r['gw'],
                       carried_from_earlier_gw=r['gw'] < d['gw'], tier='strict' if strict else 'archive_clock_conditional')
            prior = previous.get(r['fpl_element'])
            signature = (r['raw_status'], r['raw_news'], r['news_added'])
            row['unchanged_news_since_previous_gw'] = bool(prior and prior[0] == signature)
            # Re-scope chances for the new GW, never carry an old chance as a fresh probability.
            chance = r['chance_this_round'] if r['payload_current_event'] == d['gw'] else r['chance_next_round'] if r['payload_next_event'] == d['gw'] else None
            row['scoped_chance'] = chance
            row['normalized_availability_state'] = normalized(r['raw_status'], chance, prior[1] if prior else None)
            previous[r['fpl_element']] = (signature, r['raw_status'])
            assert timestamp(row['effective_at']) < cutoff
            out.append(row)
        result.extend(out)
        coverage.append(dict(gw=d['gw'], cutoff=d['cutoff'], tier='strict' if strict else 'archive_clock_conditional',
            usable_player_rows=len(out), mapped=sum(r['identity_status'] == 'mapped' for r in out),
            unresolved=sum(r['identity_status'] != 'mapped' for r in out),
            carry_forward_rows=sum(r['carried_from_earlier_gw'] for r in out),
            unchanged_news_rows=sum(r['unchanged_news_since_previous_gw'] for r in out),
            selected_observation=newest,
            observation_age_hours=(cutoff-timestamp(newest)).total_seconds()/3600 if newest else None,
            post_deadline_excluded_rows=sum(r['gw'] == d['gw'] and timestamp(r['effective_at'] if strict else r['archive_clock_effective_at']) >= cutoff for r in observations)))
    return result, coverage

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', type=Path, default=ROOT/'work/core.sqlite3')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--rebuild', type=Path)
    a = ap.parse_args()
    if a.out.exists():
        raise FileExistsError('Append-only: choose a new output version')
    if a.rebuild:
        observations = read_gz(a.rebuild/'observations.jsonl.gz')
        sources = json.loads((a.rebuild/'source_manifest.json').read_text())['sources']
        deadlines = json.loads((a.rebuild/'deadlines.json').read_text())
    else:
        cache = ROOT/'.cache/team-news-audit'
        cache.mkdir(parents=True, exist_ok=True)
        observations, sources, deadlines = collect(a.db, cache)
    a.out.mkdir(parents=True)
    write_gz(a.out/'observations.jsonl.gz', observations)
    write_json(a.out/'source_manifest.json', dict(archive=ARCHIVE, pinned_head=PIN, sources=sources))
    write_json(a.out/'deadlines.json', deadlines)
    coverage = []
    for strict, name in [(True, 'predeadline_strict'), (False, 'predeadline_archive_clock')]:
        rows, c = project(observations, deadlines, strict)
        write_gz(a.out/(name+'.jsonl.gz'), rows)
        coverage.extend(c)
    with (a.out/'coverage.csv').open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(coverage[0])); w.writeheader(); w.writerows(coverage)
    summary = dict(season='2025-26', observation_rows=len(observations), snapshots=len(sources),
                   verified_snapshots=sum(s['timing_verified'] for s in sources),
                   identity_counts={k: sum(r['identity_status']==k for r in observations) for k in ['mapped','unresolved','ambiguous']},
                   raw_status_counts={k: sum(r['raw_status']==k for r in observations) for k in sorted({r['raw_status'] for r in observations})},
                   future_news_rows=sum(r['future_news_timestamp'] for r in observations),
                   deadline_mismatch_snapshots=sum(not s['deadline_matches'] for s in sources),
                   coverage=coverage, strict_target_leakage=0,
                   limitations=['Two sampled captures per GW, not every historical update.', 'Server job completion (or run updated upper bound) is a conservative inferred availability bound, not official news publication time.', 'Clock-only archive timestamps remain unverified and are excluded from strict tier.'])
    write_json(a.out/'summary.json', summary)
    write_json(a.out/'SHA256_MANIFEST.json', {p.name: sha(p.read_bytes()) for p in sorted(a.out.iterdir()) if p.is_file()})
    print(json.dumps({k:v for k,v in summary.items() if k != 'coverage'}, indent=2))

if __name__ == '__main__':
    main()
