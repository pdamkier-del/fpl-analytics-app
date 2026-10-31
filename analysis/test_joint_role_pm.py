"""Full two-season paired PM gate for the opt-in role transport candidate."""
import argparse,copy,gzip,json,sqlite3
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import replace,asdict
from pathlib import Path

import numpy as np
import pandas as pd

from test_joint_role_candidate import histories
from audit_correctness_historical import decode
from gk_joint_bridge import observations,DurationHistory,prepare,UNKNOWN
from b_chain_contract import prepare_match
from joint_role_bridge import apply_assignment
from fpl_v1_1_model.experimental_joint_role_assignment import role_lineup_sampler
from fpl_v1_1_model.joint_simulator import simulate_many

ROOT=Path(__file__).resolve().parents[1]


def evaluate(task):
    season,fx,seed,baseline,candidate,distributions=task;rows=[]
    for arm,data in [('baseline',baseline),('candidate',candidate)]:
        inp=decode(copy.deepcopy(data))
        with role_lineup_sampler(distributions if arm=='candidate'else{}):
            sim=simulate_many(inp,n=400,seed=seed)
        for p in inp.players:
            if p.player_id.startswith(UNKNOWN):continue
            s=sim[p.player_id]
            rows.append(dict(season=season,fixture_uuid=fx,player_uuid=p.player_id,
                arm=arm,xp=s['xPts'],sim_minutes=s['expected_minutes']))
    return rows


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--workers',type=int,default=4)
    args=ap.parse_args();out=args.out
    decision=json.loads((out/'decision.json').read_text());strength=decision['selected_strength']
    if not decision['mm_gate_passed']:raise ValueError('MM gate must pass before PM')
    protocol=dict(draws=400,fixtures=501,baseline='existing unified B mean-preserving historical arm',
        candidate='same event inputs, new MM marginals and whole tactical lineups; same seed',
        acceptance='xP MAE delta <=0.005 each season, played MAE delta <=0.02; absolute bias increases <=0.02',
        limitations=['Reused research periods; historical clock proxies','Monte Carlo order changes; seed pairing is not exact common random numbers',
                     'No independent certification or full-season transfer-policy result'])
    (out/'pm-protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    f=pd.read_csv(out/'predictions.csv.gz',low_memory=False)
    with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True)as db:
        core=pd.read_sql_query('SELECT season,fixture_uuid,player_uuid,team_id,minutes,total_points FROM player_fixture_observations WHERE is_final=1',db)
    hist=histories(core);obs=observations(ROOT);caches={};tasks=[];audit=[]
    for season in ('2024-25','2025-26'):
        records=[json.loads(line)for line in gzip.open(ROOT/f'analysis/results/general-conversion-20261020/{season}_prepared.jsonl.gz','rt')]
        for r in records:
            g=f[f.season.eq(season)&f.fixture_uuid.eq(r['core_fixture'])].copy();candidate,dist,receipt=apply_assignment(g,hist[season],strength=strength)
            if not np.allclose(candidate.p,g.candidate_p,atol=5e-7,rtol=0) or not np.allclose(candidate.q,g.candidate_q,atol=5e-7,rtol=0):
                raise ValueError('PM role mixture does not reproduce MM candidate')
            inp=decode(copy.deepcopy(r['input']));by=g.set_index('player_uuid')
            if set(by.index)!={p.player_id for p in inp.players}:raise ValueError('Frozen roster differs')
            inp=replace(inp,players=tuple(replace(p,p_start=float(by.loc[p.player_id,'p']),
                p_cameo_given_bench=float(by.loc[p.player_id,'q']),start_minutes_mean=float(by.loc[p.player_id,'s']),
                cameo_minutes_mean=float(by.loc[p.player_id,'c']))for p in inp.players))
            cut=r['cutoff']
            if cut not in caches:caches[cut]=DurationHistory(obs,cut)
            inp,_,_=prepare(inp,g,caches[cut]);inp=prepare_match(inp)
            by=candidate.set_index('player_uuid')
            alt=replace(inp,players=tuple(p if p.is_keeper else replace(p,p_start=float(by.loc[p.player_id,'p']),
                p_cameo_given_bench=float(by.loc[p.player_id,'q']))for p in inp.players))
            # Team IDs in the frozen simulator are string representations of
            # canonical IDs; verify this instead of mapping display names.
            if not set(dist)<=set(map(int,(inp.home_team,inp.away_team))):raise ValueError('Team mismatch')
            tasks.append((season,r['core_fixture'],r['seed'],asdict(inp),asdict(alt),dist))
            audit.extend(dict(season=season,fixture_uuid=r['core_fixture'],**a)for a in receipt)
    rows=[]
    with ProcessPoolExecutor(max_workers=args.workers)as pool:
        for i,future in enumerate(as_completed([pool.submit(evaluate,t)for t in tasks])):
            rows.extend(future.result())
            if (i+1)%20==0 or i+1==len(tasks):print('Role PM fixtures',i+1,'/',len(tasks),flush=True)
    predictions=pd.DataFrame(rows).merge(core[['season','fixture_uuid','player_uuid','minutes','total_points']],
        on=['season','fixture_uuid','player_uuid'],validate='many_to_one',how='left')
    if predictions.total_points.isna().any():raise ValueError('Missing actuals')
    archived=pd.read_csv(ROOT/'analysis/results/unified-b-chain-20261021/predictions.csv.gz')
    archived=archived[archived.arm.eq('mean_preserving')]
    check=predictions[predictions.arm.eq('baseline')].merge(archived,on=['season','fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('','_archived'))
    error=float(abs(check.xp-check.xp_archived).max())
    if error>1e-9 or len(check)!=len(archived):raise ValueError('Historical B baseline no longer reproduced: '+str(error))
    metrics=[];passed=True;uncertainty=[];rng=np.random.default_rng(20261022)
    for (season,arm),g in predictions.groupby(['season','arm']):
        err=g.xp-g.total_points
        metrics.append(dict(season=season,arm=arm,rows=len(g),fixtures=int(g.fixture_uuid.nunique()),xp_mae=float(abs(err).mean()),
                            xp_bias=float(err.mean()),played_xp_mae=float(abs(err[g.minutes.gt(0)]).mean())))
    metric=pd.DataFrame(metrics)
    for season in ('2024-25','2025-26'):
        m=metric[metric.season.eq(season)].set_index('arm');a=m.loc['candidate'];b=m.loc['baseline']
        passed &= a.xp_mae-b.xp_mae<=.005 and a.played_xp_mae-b.played_xp_mae<=.02 and abs(a.xp_bias)-abs(b.xp_bias)<=.02
        g=predictions[predictions.season.eq(season)]
        pair=g[g.arm.eq('candidate')].merge(g[g.arm.eq('baseline')],on=['season','fixture_uuid','player_uuid'],suffixes=('','_b'),validate='one_to_one')
        pair['delta']=abs(pair.xp-pair.total_points)-abs(pair.xp_b-pair.total_points)
        blocks=pair.groupby('fixture_uuid').delta.agg(['sum','size']).to_numpy();draw=blocks[rng.integers(len(blocks),size=(4000,len(blocks)))].sum(axis=1)
        uncertainty.append(dict(season=season,mae_delta=float(pair.delta.mean()),fixture_bootstrap95=np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist()))
    predictions.to_csv(out/'pm-predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    metric.to_csv(out/'pm-metrics.csv',index=False)
    (out/'pm-role-receipts.json.gz').write_bytes(gzip.compress((json.dumps(audit,sort_keys=True,separators=(',',':'))+'\n').encode(),mtime=0))
    report=dict(passed=bool(passed),fixtures=len(tasks),baseline_max_xp_error=error,paired_uncertainty=uncertainty,enabled=False)
    (out/'pm-decision.json').write_text(json.dumps(report,indent=2)+'\n');print(metric.to_string(index=False));print(json.dumps(report,indent=2))


if __name__=='__main__':main()
