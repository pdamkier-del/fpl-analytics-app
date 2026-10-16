#!/usr/bin/env python3
"""Factorial selected individual MM x unchanged PM / fixed player PM v2."""
import argparse,copy,hashlib,json,sys
from pathlib import Path
from dataclasses import asdict
from contextlib import ExitStack
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from audit_capture_io import checked_records,write_records,write_frame
from audit_correctness_historical import decode
from experiment_mm_pm import POINT_COMPONENTS,score
from fpl_v1_1_model.joint_simulator import simulate_many
from fpl_v1_1_model.experimental_player_pm import shadow_player_intensity
from research_player_pm_v2 import Factory,data
from research_pm_conversion import target_records,deadlines
from individual_mm_validation import save


def evaluate(task):
    record,draws,cache,fingerprint=task
    sig=hashlib.sha256(json.dumps(dict(record=record,draws=draws,fingerprint=fingerprint),sort_keys=True).encode()).hexdigest();path=Path(cache)/(record['core_fixture']+'.jsonl.gz')
    if path.exists():
        v=checked_records(path)[0]
        if v['signature']==sig:return v['rows']
    rows=[]
    for name,item in record['arms'].items():
        inp=decode(copy.deepcopy(item['input']))
        if name=='original_MM__original_PM' and record.get('baseline_sim'):
            sim=record['baseline_sim']
        else:
            with ExitStack() as stack:
                if item['spec'] is not None:stack.enter_context(shadow_player_intensity(item['spec']))
                sim=simulate_many(inp,n=draws,seed=record['seed'])
        if name=='original_MM__original_PM' and any(sim[k]['xPts']!=v for k,v in record['reference'].items()):raise ValueError('Frozen original PM reference mismatch')
        for p in inp.players:
            if p.player_id not in record['reference']:continue
            v=sim[p.player_id]
            if not np.isclose(sum(v[k] for k in POINT_COMPONENTS),v['xPts'],atol=1e-10,rtol=0):raise ValueError('Point sum mismatch')
            rows.append(dict(fixture_uuid=record['core_fixture'],gw=record['origin'],player_uuid=p.player_id,team_id=int(p.team),mode=name,xp=v['xPts'],sim_minutes=v['expected_minutes'],pos=p.position,**{k:v[k] for k in POINT_COMPONENTS}))
    write_records(path,[dict(signature=sig,rows=rows)]);return rows


def summarize(frame,base):
    result={};ref=frame[frame['mode'].eq(base)]
    for mode,g in frame.groupby('mode'):
        m=score(g);pair=g.merge(ref[['fixture_uuid','player_uuid','xp']],on=['fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('','_base'))
        m['paired']={}
        for cluster in ['fixture_uuid','team_id']:
            b=pd.DataFrame(dict(cluster=pair[cluster],da=abs(pair.xp-pair.total_points)-abs(pair.xp_base-pair.total_points),se=(pair.xp-pair.total_points)**2,sb=(pair.xp_base-pair.total_points)**2)).groupby('cluster').agg(da=('da','sum'),se=('se','sum'),sb=('sb','sum'),n=('da','size')).to_numpy();rng=np.random.default_rng(20261015);draw=b[rng.integers(len(b),size=(2000,len(b)))].sum(1)
            m['paired'][cluster]=dict(mae_delta=float((abs(pair.xp-pair.total_points)-abs(pair.xp_base-pair.total_points)).mean()),mae_interval95=np.quantile(draw[:,0]/draw[:,3],[.025,.975]).tolist(),rmse_interval95=np.quantile(np.sqrt(draw[:,1]/draw[:,3])-np.sqrt(draw[:,2]/draw[:,3]),[.025,.975]).tolist())
        m['component_mean_delta']={k:float(g[k].mean()-ref[k].mean()) for k in POINT_COMPONENTS};result[mode]=m
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--season',required=True);ap.add_argument('--inputs',required=True);ap.add_argument('--out',default='analysis/results/individual-mm-20261015');ap.add_argument('--workers',type=int,default=2);ap.add_argument('--limit',type=int,default=0);a=ap.parse_args();out=Path(a.out)
    obs,teams,names,audit=data('work/core.sqlite3');factory=Factory(obs,a.season);cuts=deadlines(ROOT/'analysis/results/mm-research-20261014');records=target_records(a.inputs,'work/core.sqlite3',a.season)
    cfg=json.loads((ROOT/'analysis/results/player-pm-v2-20261015/selection.json').read_text())['selected']['hybrid'];selected=json.loads((out/'selection.json').read_text())['selected_arm']
    if a.limit:records=records[:a.limit]
    prepared=[]
    for r in records:
        arm={};cut=cuts[a.season][r['origin']]
        for mm,raw in [('original_MM',r['input']),('role_MM',r['candidate_inputs'][selected]),('control_MM',r['candidate_inputs']['same_logistic_without_role'])]:
            inp=decode(copy.deepcopy(raw));alt,spec=factory.build(inp,cut,cfg)
            arm[mm+'__original_PM']=dict(input=asdict(inp),spec=None)
            arm[mm+'__player_PM_v2']=dict(input=asdict(alt),spec=spec)
        prepared.append(dict(baseline_sim=r.get('baseline_sim'),core_fixture=r['core_fixture'],origin=r['origin'],seed=r['seed'],arms=arm,reference=r['reference']))
    write_records(out/f'{a.season}_pm_factorial_inputs.jsonl.gz',prepared)
    cache=out/('pm_cache_'+a.season);cache.mkdir(exist_ok=True);rows=[]
    fingerprint={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['scripts/individual_mm_pm_replay.py','src/fpl_v1_1_model/joint_simulator.py','src/fpl_v1_1_model/experimental_player_pm.py']}
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        jobs=[pool.submit(evaluate,(r,400,str(cache),fingerprint)) for r in prepared]
        for i,f in enumerate(as_completed(jobs)):
            rows.extend(f.result())
            if (i+1)%10==0:print('Individual-MM full PM',a.season,i+1,'/',len(prepared),flush=True)
    truth=obs[obs.season.eq(a.season)][['fixture_uuid','player_uuid','total_points','minutes']];p=pd.DataFrame(rows).merge(truth,on=['fixture_uuid','player_uuid'],validate='many_to_one',how='left')
    if p[['total_points','minutes']].isna().any().any():raise ValueError('Missing target truth')
    write_frame(out/f'{a.season}_pm_predictions.csv.gz',p)
    if a.season=='2024-25':p=p[p.gw.ge(22)]
    result={}
    for pm in ['original_PM','player_PM_v2']:
        g=p[p['mode'].str.endswith('__'+pm)];result[pm]=summarize(g,'original_MM__'+pm)
        result[pm+'_role_vs_logistic_control']=summarize(g[g['mode'].str.startswith(('role_MM','control_MM'))],'control_MM__'+pm)
    save(out/f'{a.season}_pm_report.json',dict(fixtures=len(records),draws=400,original_exact=True,results=result,pm_v2_config=cfg,fingerprint=fingerprint,locked_model_active=False,promotion_allowed=False,limitations=['Frozen archived originals; all MM-dependent GA/DC/discipline/own-goal inputs rebuilt and baseline checked','Original independent start simulator retained in both arms; expected-XI constraints do not repair its realized-XI physics','Original scoring and fixed PM v2 configuration retained; no PM research retuning','Single paired seed per fixture; interval does not include all Monte Carlo uncertainty','Research seasons and publication proxies reused; not independent certification']))
    print('PM factorial completed',a.season,len(records),flush=True)
if __name__=='__main__':main()
