"""Resumable, audit-only draws. All outcomes remain under an oracle label."""
import argparse,copy,gzip,hashlib,inspect,json,os,resource,time
from dataclasses import asdict
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
from precision_audit.dataset import load,dump
from precision_audit.oracles import OracleTimeline,simulate
from test_separated_goal_head import decode
from gk_joint_bridge import UNKNOWN,marginals
from fpl_v1_1_model.point_accounting import point_components
FIELDS=['points','minutes','started','goals','assists','clean_sheet','bonus','appearance_pts','goal_pts','assist_pts','cs_pts','save_pts','penalty_save_pts','dc_pts','negative_pts','gc_pts']

def run(record,n,seed,mask=0,split_streams=False):
    inp=decode(copy.deepcopy(record['input']));start=time.perf_counter();timeline=OracleTimeline(inp,record.get('dist',{}),record.get('actual',{}),mask)
    kernel_seconds=time.perf_counter()-start;ps=list(inp.players);samples=np.zeros((n,len(ps),len(FIELDS)),np.int16);rng=np.random.default_rng(seed);timings={};start=time.perf_counter()
    for i in range(n):
        if split_streams:
            minute_rng=np.random.default_rng(np.random.SeedSequence([seed,i,1]));event_rng=np.random.default_rng(np.random.SeedSequence([seed,i,2]))
        else:minute_rng=event_rng=rng
        t=timeline.sample(minute_rng);result=simulate(inp,event_rng,t,record['goals']if mask&4 else None,point_minutes=timeline.point_minutes)
        for j,p in enumerate(ps):
            r=result[p.player_id];components=point_components(p.position,p.is_keeper,r);samples[i,j]=[getattr(r,k)for k in FIELDS[:7]]+[components[k]for k in FIELDS[7:]]
        if i+1 in [400,2000,10000]:timings[i+1]=time.perf_counter()-start
    rows=[]
    for size in [x for x in [400,2000,10000]if x<=n]or[n]:
        sub=samples[:size];means=sub.mean(axis=0);sd=sub.std(axis=0,ddof=1)if size>1 else np.zeros_like(means)
        for j,p in enumerate(ps):
            if p.player_id.startswith(UNKNOWN):continue
            meta=record['meta'].get(p.player_id,{})
            rows.append(dict(season=record['season'],fixture_uuid=record['fixture_uuid'],player_uuid=p.player_id,draws=size,seed=seed,mask=mask,**meta,**{k:float(means[j,c])for c,k in enumerate(FIELDS)},**{'mcse_'+k:float(sd[j,c]/np.sqrt(size))for c,k in enumerate(FIELDS[:7])},p_goal=float(np.mean(sub[:,j,3]>0)),p_assist=float(np.mean(sub[:,j,4]>0)),p60=float(np.mean(sub[:,j,1]>=60)),p90=float(np.mean(sub[:,j,1]==90)),p10=float(np.mean(sub[:,j,0]>=10))))
    if mask==0:
        for row in rows:
            pid=row['player_uuid']
            if pid in timeline.kernel.moments:
                m=timeline.kernel.moments[pid];row.update(analytic_minutes=m['x'],analytic_start=m['p'],analytic_p60=m['p60'],analytic_p90=m['p90'])
            else:
                p=next(p for p in ps if p.player_id==pid);mass=marginals([q for q in ps if q.team==p.team and q.is_keeper])[pid];row.update(analytic_minutes=float(mass@np.arange(91)),analytic_start=p.p_start,analytic_p60=float(mass[60:].sum()),analytic_p90=float(mass[90]))
    receipt=dict(fixture_uuid=record['fixture_uuid'],season=record['season'],mask=mask,seed=seed,draws=n,kernel_seconds=kernel_seconds,prefix_simulation_seconds=timings,total_seconds=kernel_seconds+time.perf_counter()-start,process_peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,stored_array_bytes=int(samples.nbytes),same_draw_prefix_across_N=True,event_streams_separate_from_minute_streams=split_streams)
    selected=(record['season']=='2026-27' or record['gw']in [24,28,32])and mask==0
    return rows,receipt,(samples[:,:,0:2],np.array([p.player_id for p in ps]))if selected else None

def cached(task):
    record,n,seed,mask,split,folder=task;folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    source={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [Path('analysis/precision_audit/oracles.py'),Path(__file__),*sorted(Path('src/fpl_v1_1_model').glob('*.py'))]}
    key=hashlib.sha256(json.dumps(dict(record=record,n=n,seed=seed,mask=mask,split=split,source=source),default=asdict,sort_keys=True).encode()).hexdigest();path=folder/(key+'.json.gz')
    if path.exists():return json.loads(gzip.decompress(path.read_bytes()))
    rows,receipt,samples=run(record,n,seed,mask,split)
    if samples is not None:
        target=folder/(key+'.npz');np.savez_compressed(target,points_minutes=samples[0],players=samples[1]);receipt['samples_file']=str(target)
    result=dict(rows=rows,receipt=receipt);temp=folder/(key+f'.{os.getpid()}.tmp');temp.write_bytes(gzip.compress(json.dumps(result,allow_nan=False).encode(),mtime=0));temp.replace(path)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=['baseline','oracle','mc'],required=True);p.add_argument('--workers',type=int,default=4);p.add_argument('--limit',type=int);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);records=load(a.inputs)
    if a.mode=='oracle':
        records=[r for r in records if r.get('oracle_eligible')];chosen=[]
        for season in sorted({r['season']for r in records}):
            group=sorted([r for r in records if r['season']==season],key=lambda r:(r['gw'],r['fixture_uuid']));indices=np.unique(np.linspace(0,len(group)-1,min(24,len(group)),dtype=int));chosen.extend(group[i]for i in indices)
        records=chosen
    if a.limit:records=records[:a.limit]
    tasks=[]
    for record in records:
        for rep in range(6 if a.mode=='mc'else 3):
            for mask in (range(8)if a.mode=='oracle'else[0]):
                seed=20261101+int(hashlib.sha256((record['season']+record['fixture_uuid']).encode()).hexdigest()[:7],16)+rep*1000003
                tasks.append((record,10000 if a.mode=='mc'else 400,seed,mask,a.mode=='oracle',str(a.out/'cache')))
    results=[]
    with ProcessPoolExecutor(max_workers=a.workers)as pool:
        for i,f in enumerate(as_completed([pool.submit(cached,t)for t in tasks])):
            results.append(f.result())
            if (i+1)%10==0 or i+1==len(tasks):print(a.mode,'completed',i+1,'/',len(tasks),flush=True)
    import pandas as pd
    rows=pd.DataFrame([r for result in results for r in result['rows']]).sort_values(['season','fixture_uuid','player_uuid','draws','seed','mask']);rows.to_csv(a.out/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0});(a.out/'receipts.json').write_text(json.dumps([r['receipt']for r in results],indent=2)+'\n')
    (a.out/'cohort.json').write_text(json.dumps([dict(season=r['season'],fixture_uuid=r['fixture_uuid'],gw=r['gw'])for r in records],indent=2)+'\n')
if __name__=='__main__':main()
