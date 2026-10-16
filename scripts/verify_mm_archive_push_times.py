"""Recover independent GitHub server push bounds from checksumed GH Archive.

Do not relabel commit-author clocks as server clocks. Require exact repo,
branch, head AND parent; archived API event time supplies a separate bound.
"""
import concurrent.futures,datetime as dt,gzip,hashlib,io,json
from pathlib import Path
import requests
from audit_fpl_team_news import timestamp,iso,write_json,write_gz,sha
ROOT=Path(__file__).resolve().parents[1]
def event_matches(event,source):
    p=event.get('payload',{})
    return event.get('type')=='PushEvent'and event.get('public')is True and event.get('repo',{}).get('id')==359131220 and event.get('repo',{}).get('name')=='Randdalf/fplcache'and p.get('ref')=='refs/heads/main'and p.get('head')==source['source_commit']and p.get('before')==source['parent_commit']

def verify(source):
    s=dict(source);clock=timestamp(s['effective_at']);url='https://data.gharchive.org/'+clock.strftime('%Y-%m-%d-')+str(clock.hour)+'.json.gz';proof=dict(url=url)
    try:
        response=requests.get(url,timeout=(20,90));response.raise_for_status();raw=response.content;proof.update(archive_sha256=sha(raw),archive_bytes=len(raw));events=[]
        with gzip.GzipFile(fileobj=io.BytesIO(raw))as z:
            for line in z:
                if b'Randdalf/fplcache'not in line:continue
                event=json.loads(line)
                if event_matches(event,s):events.append((event,sha(line)))
        if len(events)!=1:raise ValueError('Missing or ambiguous matching push event')
        e,digest=events[0];proof.update(event_id=e['id'],event_sha256=digest,created_at=e['created_at'],repo=e['repo'],payload={k:e['payload'][k]for k in ['ref','head','before']})
        if not all(v['identical_to_inspected_pipeline']for v in s['pipeline'].values()):raise ValueError('Unverified fetch-before-push pipeline')
        bound=max(clock,timestamp(e['created_at']));s.update(timing_verified=True,effective_at=iso(bound),timestamp_basis='gharchive_recorded_github_api_push_event',gharchive=proof)
    except Exception as exc:proof['error']=str(exc);s['gharchive']=proof
    print('Push-clock',s['gw'],s['timing_verified'],proof.get('error',''),flush=True);return s

def main():
    p=ROOT/'work/news-2024';m=json.loads((p/'source_manifest.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:sources=list(pool.map(verify,m['sources']))
    by={r['source_commit']:r for r in sources if r.get('timing_verified')};rows=[]
    with gzip.open(p/'observations.jsonl.gz','rt')as z:
        for l in z:
            r=json.loads(l);s=by.get(r['source_commit'])
            if s:r.update(timing_verified=True,effective_at=s['effective_at'],timestamp_basis=s.get('timestamp_basis'))
            r['strict_eligible']=bool(r['timing_verified']and r['deadline_matches']and timestamp(r['effective_at'])<timestamp(r['cutoff'])and r['identity_status']=='mapped'and(not r['news_added']or timestamp(r['news_added'])<=timestamp(r['effective_at'])))
            rows.append(r)
    out=ROOT/'work/news-2024-push-verified';out.mkdir(parents=True,exist_ok=True);m['sources']=sources;m['independent_clock_source']='GH Archive hourly checksumed GitHub Events API; exact push head/parent identity, not forged commit-author time';write_json(out/'source_manifest.json',m);write_gz(out/'observations.jsonl.gz',rows);write_gz(out/'predeadline_strict.jsonl.gz',[r for r in rows if r['strict_eligible']]);write_json(out/'SHA256_MANIFEST.json',{x.name:sha(x.read_bytes())for x in out.glob('*')if x.is_file()});print('Verified2024 snapshots',len(by),'strict rows',sum(r['strict_eligible']for r in rows),flush=True)
if __name__=='__main__':main()
