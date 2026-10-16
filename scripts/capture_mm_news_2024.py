"""Extend existing immutable FPL capture audit to2024; no forecast fitting."""
import argparse,datetime as dt,hashlib,json,lzma,re,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts')]
from audit_fpl_team_news import API,ARCHIVE,PIN,UTC,get,getj,iso,timestamp,sha,certified_time,normalized,write_json,write_gz
from individual_mm_evidence import load_frame
def capture(out):
    out.mkdir(parents=True,exist_ok=True);cache=out/'http-cache';cache.mkdir(exist_ok=True)
    frame=load_frame(ROOT/'work/mm-source/2024-25_candidates.npz');f=frame[frame['mode'].eq('original')];deadlines=f[['gw','cutoff']].drop_duplicates().sort_values('gw').to_dict('records')
    if len(deadlines)!=33:raise ValueError('Missing source deadlines')
    trees={2024:'f9328e0127ad0ae24c32e4d4b55014067134b896',2025:'44e26d825d98da8f171d2d0d07d20accfc2baf6c'};paths=[]
    for year,tree in trees.items():
        j=getj(API+'/git/trees/'+tree+'?recursive=1',cache)
        if j.get('truncated'):raise ValueError('Truncated archive tree')
        for entry in j['tree']:
            m=re.fullmatch(r'(\d+)/(\d+)/(\d{2})(\d{2})\.json\.xz',entry['path'])
            if m:
                month,day,hour,minute=map(int,m.groups());paths.append(dict(path=f'cache/{year}/'+entry['path'],sha=entry['sha'],nominal=iso(dt.datetime(year,month,day,hour,minute,tzinfo=UTC))))
    paths.sort(key=lambda r:r['nominal']);ids={};codes={}
    with sqlite3.connect(ROOT/'work/core.sqlite3')as c:
        for pid,ext in c.execute("SELECT DISTINCT player_uuid,external_id FROM player_id_mapping WHERE id_namespace='fpl_element' AND season='2024-25'"):ids.setdefault(str(ext),set()).add(pid)
        for pid,ext in c.execute("SELECT DISTINCT player_uuid,external_id FROM player_id_mapping WHERE id_namespace='fpl_code'"):codes.setdefault(pid,set()).add(str(ext))
    sources=[];rows=[]
    for d in deadlines:
        cut=timestamp(d['cutoff']);available=[r for r in paths if timestamp(r['nominal'])<cut]
        if not available:sources.append(dict(gw=d['gw'],error='No prior capture'));continue
        p=available[-1];src=dict(gw=d['gw'],cutoff=d['cutoff'],**p)
        try:
            commit=getj(API+'/commits?sha='+PIN+'&path='+p['path']+'&per_page=1',cache)[0];parent=commit['parents'][0]['sha'];runs=getj(API+'/actions/runs?head_sha='+parent+'&per_page=100',cache)
            if runs['total_count']>100:raise ValueError('Truncated run search')
            effective,verified,run=certified_time(timestamp(p['nominal']),timestamp(commit['commit']['committer']['date']),parent,runs['workflow_runs']);job=None
            if run:
                jobs=getj(API+'/actions/runs/'+str(run['id'])+'/jobs?per_page=100',cache)
                if jobs['total_count']>100:raise ValueError('Truncated jobs')
                good=[r for r in jobs['jobs']if r.get('name')=='cache'and r.get('conclusion')=='success'and r.get('completed_at')and timestamp(r['started_at'])<=timestamp(commit['commit']['committer']['date'])<=timestamp(r['completed_at'])]
                if good:job=min(good,key=lambda r:r['completed_at']);effective=max(timestamp(p['nominal']),timestamp(commit['commit']['committer']['date']),timestamp(job['completed_at']))
            pipeline={};ok=True
            for name in ['cache.py','.github/workflows/cache.yml']:
                old=get('https://raw.githubusercontent.com/'+ARCHIVE+'/'+parent+'/'+name,cache);pinned=get('https://raw.githubusercontent.com/'+ARCHIVE+'/'+PIN+'/'+name,cache);pipeline[name]=dict(sha256=sha(old),identical_to_inspected_pipeline=old==pinned);ok=ok and old==pinned
            verified=verified and ok;url='https://raw.githubusercontent.com/'+ARCHIVE+'/'+commit['sha']+'/'+p['path'];raw=get(url,cache)
            if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=p['sha']:raise ValueError('Blob mismatch')
            payload=json.loads(lzma.decompress(raw));event=next(e for e in payload['events']if e['id']==d['gw']);matches=timestamp(event['deadline_time'])==cut;current=next((e['id']for e in payload['events']if e.get('is_current')),None);nextgw=next((e['id']for e in payload['events']if e.get('is_next')),None);teams={t['id']:t['name']for t in payload['teams']}
            src.update(source_url=url,source_commit=commit['sha'],raw_sha256=sha(raw),parent_commit=parent,run_id=run['id']if run else None,job_id=job['id']if job else None,effective_at=iso(effective),timing_verified=bool(verified),pipeline=pipeline,deadline_matches=matches,players=len(payload['elements']))
            for e in payload['elements']:
                found=ids.get(str(e['id']),set());pid=next(iter(found))if len(found)==1 else None;mapped=pid is not None and str(e['code'])in codes.get(pid,set());news=e.get('news_added');chance=e.get('chance_of_playing_this_round')if current==d['gw']else e.get('chance_of_playing_next_round')if nextgw==d['gw']else None;eligible=bool(verified and matches and effective<cut and mapped and(not news or timestamp(news)<=effective))
                rows.append(dict(season='2024-25',gw=d['gw'],cutoff=d['cutoff'],player_uuid=pid if mapped else None,fpl_element=e['id'],fpl_code=e['code'],player_name=e['first_name']+' '+e['second_name'],team=teams[e['team']],team_id=e['team'],observed_at=p['nominal'],effective_at=iso(effective),source='official_fpl_bootstrap_via_randdalf_archive',source_url=url,source_id=commit['sha']+':'+p['path'],source_commit=commit['sha'],raw_status=e.get('status'),raw_news=e.get('news'),news_added=news,scoped_chance=chance,normalized_availability_state=normalized(e.get('status'),chance),identity_status='mapped'if mapped else'unresolved',timing_verified=bool(verified),deadline_matches=matches,strict_eligible=eligible,payload_current_event=current,payload_next_event=nextgw))
        except Exception as exc:src['error']=str(exc)
        sources.append(src);print('2024 capture',d['gw'],'verified',src.get('timing_verified'),src.get('error',''),flush=True)
    write_gz(out/'observations.jsonl.gz',rows);write_gz(out/'predeadline_strict.jsonl.gz',[r for r in rows if r['strict_eligible']]);write_json(out/'source_manifest.json',dict(archive=ARCHIVE,pin=PIN,sources=sources,selection='One nearest nominal predeadline capture perGW6-38; no carry-forward; source deadline must equal frozen MM origin',limitations=['Missing or unverifiable run clocks excluded, not imputed','FPL flag is not detailed medical clearance','Not all intraday updates observed']))
    write_json(out/'SHA256_MANIFEST.json',{p.name:sha(p.read_bytes())for p in [out/'observations.jsonl.gz',out/'predeadline_strict.jsonl.gz',out/'source_manifest.json']})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'work/news-2024');a=p.parse_args();capture(a.out)
