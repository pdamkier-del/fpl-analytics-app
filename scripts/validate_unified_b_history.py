"""Frozen two-season B PM duration ablation, with past-snapshot penalty roles.

No current penalty roles are replayed backwards. 2024 source clocks are
archival proxies, not independently verified publication timestamps.
"""
import argparse,copy,gzip,hashlib,json,lzma,sqlite3
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict,replace
from pathlib import Path
import numpy as np
import pandas as pd
from individual_mm_evidence import load_frame
from audit_correctness_historical import decode
from gk_joint_bridge import observations,DurationHistory,prepare,UNKNOWN
from b_chain_contract import prepare_match
from mm_locked_bridge import locked_sampler_expectation
from fpl_v1_1_model.joint_simulator import simulate_many

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/unified-b-chain-20261021'


def evaluate(task):
    season,fx,seed,arms=task
    rows=[]
    for arm,data in arms.items():
        inp=decode(copy.deepcopy(data));sim=simulate_many(inp,n=400,seed=seed)
        for p in inp.players:
            if p.player_id.startswith(UNKNOWN):continue
            s=sim[p.player_id]
            rows.append(dict(season=season,fixture_uuid=fx,player_uuid=p.player_id,arm=arm,xp=s['xPts'],sim_minutes=s['expected_minutes']))
    return rows


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);ap.add_argument('--limit',type=int,default=0);a=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    protocol=dict(version=1,cohort='all archived 501 fixtures; no outcome-dependent selection',draws=400,
        minute_acceptance='MAE improves both seasons; absolute minute bias improves both seasons',
        point_noninferiority='mean-preserving minus control xP MAE <=0.005 in each season; played-row MAE delta <=0.02',
        penalty_acceptance='historical 2024 role arm xP MAE delta <=0.005 relative to mean-preserving; deterministic role/availability tests required',
        limitations=['Reused development periods, not pristine holdouts','2024 rank snapshot clocks are unverified archival proxies','No pre-cutoff 2025 rank snapshots supplied; no current role backfill'])
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    frozen=load_frame(ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz');frozen=frozen[frozen['mode'].eq('B')]
    minute={}
    for season,g in frozen.groupby('season'):
        legacy=locked_sampler_expectation(g.p.to_numpy(),g.q.to_numpy(),g.s.to_numpy(),g.c.to_numpy())
        minute[season]={'rows':len(g),'start_brier_both':float(((g.p-g.y)**2).mean()),
            'control_mae':float(abs(legacy-g.minutes).mean()),'candidate_mae':float(abs(g.x-g.minutes).mean()),
            'control_bias':float((legacy-g.minutes).mean()),'candidate_bias':float((g.x-g.minutes).mean())}
    obs=observations(ROOT);cache={};tasks=[]
    identity=pd.read_csv(ROOT/'data_v1_1/derived/season_2024_25_v1/player_identity.csv').set_index('player_uuid').fpl_element.to_dict()
    clocks={r['gw']:r for r in json.loads((ROOT/'analysis/results/season-2024-25-data-audit-v1/snapshot_provenance.json').read_text())}
    ranks={};cohort={}
    for season in ('2024-25','2025-26'):
        records=[json.loads(line)for line in gzip.open( ROOT/f'analysis/results/general-conversion-20261020/{season}_prepared.jsonl.gz','rt')]
        if a.limit:records=records[:a.limit]
        cohort[season]=len(records)
        for r in records:
            inp=decode(copy.deepcopy(r['input']))
            b=frozen[frozen.season.eq(season)&frozen.fixture_uuid.eq(r['core_fixture'])].copy()
            by=b.set_index('player_uuid')
            if set(by.index)!={p.player_id for p in inp.players}:raise ValueError('Frozen B/PM roster mismatch')
            inp=replace(inp,players=tuple(replace(p,p_start=float(by.loc[p.player_id,'p']),p_cameo_given_bench=float(by.loc[p.player_id,'q']),
                start_minutes_mean=float(by.loc[p.player_id,'s']),cameo_minutes_mean=float(by.loc[p.player_id,'c']))for p in inp.players))
            cut=r['cutoff']
            if cut not in cache:cache[cut]=DurationHistory(obs,cut)
            # Same empirical GK and joint-XI process in both arms. This isolates
            # duration correction; existing GK-v2 role validation is separate.
            inp,_,_=prepare(inp,b,cache[cut])
            arms={'control':asdict(inp),'mean_preserving':asdict(prepare_match(inp))}
            if season=='2024-25':
                gw=r['origin']
                clock=clocks[gw]
                if pd.Timestamp(clock['clock_at'])>=pd.Timestamp(cut):raise ValueError('Rank snapshot after cutoff')
                if gw not in ranks:
                    path=ROOT/f'data_v1_1/raw/season_2024_25_v1/bootstrap/gw{gw}.json.xz'
                    if hashlib.sha256(path.read_bytes()).hexdigest()!=clock['source_sha256']:raise ValueError('Rank source checksum changed')
                    raw=json.loads(lzma.decompress(path.read_bytes()));ids={p['id']:p for p in raw['elements']}
                    ranks[gw]={pid:ids[int(e)]for pid,e in identity.items()if int(e)in ids}
                arms['penalty_roles']=asdict(prepare_match(inp,ranks[gw]))
            tasks.append((season,r['core_fixture'],r['seed'],arms))
    rows=[]
    with ProcessPoolExecutor(max_workers=a.workers)as pool:
        futures=[pool.submit(evaluate,t)for t in tasks]
        for i,f in enumerate(as_completed(futures)):
            rows.extend(f.result())
            if (i+1)%20==0 or i+1==len(tasks):print('B historical fixtures',i+1,'/',len(tasks),flush=True)
    frame=pd.DataFrame(rows)
    with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True)as db:
        truth=pd.read_sql_query('SELECT season,fixture_uuid,player_uuid,minutes,total_points FROM player_fixture_observations WHERE is_final=1',db)
    frame=frame.merge(truth,on=['season','fixture_uuid','player_uuid'],how='left',validate='many_to_one')
    if frame.total_points.isna().any():raise ValueError('Missing historical truth')
    metrics={}
    for (season,arm),g in frame.groupby(['season','arm']):
        e=g.xp-g.total_points;played=g.minutes.gt(0)
        metrics.setdefault(season,{})[arm]=dict(rows=len(g),fixtures=int(g.fixture_uuid.nunique()),xp_mae=float(abs(e).mean()),
            xp_bias=float(e.mean()),xp_rmse=float(np.sqrt((e**2).mean())),played_xp_mae=float(abs(e[played]).mean()),
            simulated_minute_mae=float(abs(g.sim_minutes-g.minutes).mean()))
    accepted=not a.limit
    for season,arms in metrics.items():
        accepted&=arms['mean_preserving']['xp_mae']-arms['control']['xp_mae']<=.005
        accepted&=arms['mean_preserving']['played_xp_mae']-arms['control']['played_xp_mae']<=.02
        accepted&=minute[season]['candidate_mae']<minute[season]['control_mae']and abs(minute[season]['candidate_bias'])<abs(minute[season]['control_bias'])
        if 'penalty_roles'in arms:accepted&=arms['penalty_roles']['xp_mae']-arms['mean_preserving']['xp_mae']<=.005
    frame.sort_values(['season','fixture_uuid','player_uuid','arm']).to_csv(OUT/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    report=dict(accepted=bool(accepted),cohort=cohort,minute_metrics=minute,point_metrics=metrics,protocol=protocol,
        production_changed=False,independent_certification=False,full_season_TS_return_test=False)
    (OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
    if not accepted:raise SystemExit('Unified B acceptance gate failed; no publication')


if __name__=='__main__':main()
