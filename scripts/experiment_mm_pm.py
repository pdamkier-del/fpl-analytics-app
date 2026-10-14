#!/usr/bin/env python3
"""Paired full-component MM→original PM evaluation; frozen scoring and seeds."""
import argparse,copy,hashlib,json,os,sqlite3,sys
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from audit_capture_io import checked_records,write_records
from audit_correctness_historical import decode
from fpl_v1_1_model.joint_simulator import simulate_many

POINT_COMPONENTS=['appearance_points','goal_points','assist_points','cs_points','save_points','dc_points','negative_points','gc_points','penalty_save_points','expected_bonus']

def evaluate(task):
    i,record,cache,fingerprint=task;signature=hashlib.sha256(json.dumps(dict(record=record,fingerprint=fingerprint),sort_keys=True).encode()).hexdigest();path=Path(cache)/f'{i:04d}.jsonl.gz'
    if path.exists():
        saved=checked_records(path)[0]
        if saved['signature']==signature:return saved['rows']
    rows=[]
    inputs={'original':record['input'],**record['candidate_inputs']}
    for mode,data in inputs.items():
        inp=decode(copy.deepcopy(data));sim=simulate_many(inp,n=400,seed=record['seed'])
        if mode=='original' and any(sim[pid]['xPts']!=ref for pid,ref in record['reference'].items()):raise ValueError('Frozen baseline PM not exact')
        for p in inp.players:
            if p.player_id not in record['reference']:continue
            value=sim[p.player_id]
            if not np.isclose(sum(value[k] for k in POINT_COMPONENTS),value['xPts'],atol=1e-10):raise ValueError('Point-component total mismatch')
            rows.append(dict(fixture=record['fixture'],gw=record['origin'],home=record['home'],away=record['away'],player_uuid=p.player_id,pos=p.position,mode=mode,xp=value['xPts'],sim_minutes=value['expected_minutes'],**{k:value[k] for k in POINT_COMPONENTS}))
    write_records(path,[dict(signature=signature,rows=rows)])
    return rows

def score(g):
    e=g.xp-g.total_points
    return dict(rows=len(g),mae=float(abs(e).mean()),rmse=float(np.sqrt((e**2).mean())),bias=float(e.mean()),mean_xp=float(g.xp.mean()),mean_actual=float(g.total_points.mean()),minute_mae=float(abs(g.sim_minutes-g.minutes).mean()),point_components={k:float(g[k].mean()) for k in POINT_COMPONENTS})

def summarize(p):
    metrics={};rng=np.random.default_rng(20261014)
    base=p[p['mode'].eq('original')][['fixture_uuid','player_uuid','xp']]
    for mode,g in p.groupby('mode'):
        result=score(g);pair=g.merge(base,on=['fixture_uuid','player_uuid'],suffixes=('','_base'),validate='one_to_one');d=abs(pair.xp-pair.total_points)-abs(pair.xp_base-pair.total_points)
        b=pd.DataFrame(dict(fixture=pair.fixture_uuid,delta=d)).groupby('fixture').delta.agg(['sum','size']).to_numpy();draw=b[rng.integers(len(b),size=(2000,len(b)))].sum(axis=1)
        result['paired_point_mae_delta']=float(d.mean());result['fixture_bootstrap_95_ci']=np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist()
        result['played']=score(g[g.minutes.gt(0)]);result['by_position']={k:score(v) for k,v in g.groupby('pos')}
        # Descriptive xP reliability, not a proper scoring rule for point distributions.
        bins=pd.cut(g.xp,[-np.inf,0,1,2,3,4,5,6,8,np.inf])
        result['xp_calibration']={str(k):dict(rows=len(v),mean_pred=float(v.xp.mean()),mean_actual=float(v.total_points.mean())) for k,v in g.groupby(bins,observed=True)}
        metrics[mode]=result
    return metrics

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--season',required=True);ap.add_argument('--db',default='work/core.sqlite3');ap.add_argument('--out',default='analysis/results/mm-research-20261014');ap.add_argument('--workers',type=int,default=3);ap.add_argument('--limit',type=int,default=0);a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    records=checked_records(a.inputs)
    if not a.limit and len(records)!=330:raise ValueError('Incomplete 330-fixture capture')
    if a.limit:records=records[:a.limit]
    cache=out/f'pm_cache_{a.season}';cache.mkdir(exist_ok=True)
    from importlib.metadata import version
    fingerprint=dict(script=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),numpy=version('numpy'),scipy=version('scipy'),model=hashlib.sha256((ROOT/'src/fpl_v1_1_model/joint_simulator.py').read_bytes()).hexdigest(),runtime={k:os.environ.get(k) for k in ['OPENBLAS_CORETYPE','NPY_DISABLE_CPU_FEATURES','PYTHONHASHSEED']})
    allrows=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        tasks=[pool.submit(evaluate,(i,r,str(cache),fingerprint)) for i,r in enumerate(records)]
        for i,future in enumerate(as_completed(tasks)):
            allrows.extend(future.result())
            if (i+1)%10==0:print('PM',a.season,'completed',i+1,'/',len(records),flush=True)
    with sqlite3.connect(Path(a.db).resolve().as_uri()+'?mode=ro',uri=True) as c:
        truth=pd.read_sql_query('SELECT fixture_uuid,player_uuid,total_points,minutes FROM player_fixture_observations WHERE season=? AND is_final=1',c,params=[a.season]);fx=pd.read_sql_query('SELECT fixture_uuid,home_team_id,away_team_id FROM fixtures WHERE season=?',c,params=[a.season])
    if fx.duplicated(['home_team_id','away_team_id']).any():raise ValueError('Nonunique fixture sides')
    p=pd.DataFrame(allrows).merge(fx,left_on=['home','away'],right_on=['home_team_id','away_team_id'],validate='many_to_one',how='left');p=p.merge(truth,on=['fixture_uuid','player_uuid'],validate='many_to_one',how='left',indicator=True)
    if not p._merge.eq('both').all() or p[['total_points','minutes']].isna().any().any():raise ValueError('Missing truth; cannot impute')
    p=p.sort_values(['gw','fixture_uuid','player_uuid','mode']).drop(columns='_merge');p.to_csv(out/f'{a.season}_pm_predictions.csv.gz',index=False,compression='gzip')
    periods={'all':p,'GW22_38':p[p.gw.ge(22)]}
    report=dict(classification='TEMPORAL_CANDIDATE_MM_THROUGH_UNCHANGED_FULL_PM',season=a.season,fixtures=len(records),draws=400,original_exact=True,results={k:summarize(v) for k,v in periods.items()},source_sha256=hashlib.sha256(Path(a.inputs).read_bytes()).hexdigest(),locked_model_active=False,promotion_allowed=False,limitations=['Reused baseline-development seasons; source publication availability proxies','Point coefficients and original simulator fixed; simulator-correctness candidate deliberately not combined','Independent branches change RNG consumption, bootstrap does not include all Monte Carlo uncertainty','All upstream MM-dependent GA/DC/own-goal components rebuilt through original functions','Complete historical six-GW candidate TS cells unavailable'])
    (out/f'{a.season}_pm_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(season=a.season,fixtures=len(records),results={k:{mode:{key:r[key] for key in ['rows','mae','rmse','bias','paired_point_mae_delta','fixture_bootstrap_95_ci']} for mode,r in v.items()} for k,v in report['results'].items()}),indent=2))
if __name__=='__main__':main()
