"""Frozen, general two-season gate for the physical-timeline repair candidate."""
import argparse
import copy
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from test_separated_goal_head import prepare_tasks, decode, UNKNOWN
from b_chain_contract import field_marginals
from gk_joint_bridge import marginals
from fpl_v1_1_model.experimental_joint_role_assignment import role_lineup_sampler
from fpl_v1_1_model.experimental_physical_timeline import PhysicalKernel,physical_sampler
from fpl_v1_1_model.joint_simulator import simulate_many

ROOT=Path(__file__).resolve().parents[1]


def evaluate(task):
    season,fx,seed,data,dist,factors,_=task
    original=decode(copy.deepcopy(data))
    inp=replace(original,experimental_conditional_penalties=True,
        players=tuple(replace(p,goal_weight=factors[p.player_id],penalty_fallback_weight=p.goal_weight)for p in original.players))
    base_mass={p.player_id:field_marginals(p)for p in inp.players if not p.is_keeper}
    for team in (inp.home_team,inp.away_team):
        base_mass.update(marginals([p for p in inp.players if p.team==team and p.is_keeper]))
    kernel=PhysicalKernel(inp,dist)
    for p in inp.players:
        if not p.is_keeper and abs(kernel.moments[p.player_id]['p']-p.p_start)>1e-6:
            raise ValueError('Candidate changed original start marginals')
    rows=[]
    for arm in ['baseline','candidate']:
        scope=role_lineup_sampler(dist) if arm=='baseline' else physical_sampler(kernel)
        with scope:sim=simulate_many(inp,n=400,seed=seed)
        for p in inp.players:
            if p.player_id.startswith(UNKNOWN):continue
            mass=base_mass[p.player_id] if arm=='baseline' or p.is_keeper else np.array(kernel.moments[p.player_id]['pmf'])
            rows.append(dict(season=season,fixture_uuid=fx,player_uuid=p.player_id,arm=arm,
                keeper=p.is_keeper,baseline_p_start=p.p_start,xp=sim[p.player_id]['xPts'],
                xmins=float(mass@np.arange(91)),p0=float(mass[0]),p60=float(mass[60:].sum()),p90=float(mass[90])))
    return rows


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--workers',type=int,default=2)
    args=ap.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    protocol=json.loads((out/'protocol.json').read_text())
    modelpath=ROOT/'analysis/results/nonpenalty-goal-head-20261023/final-v2/model.json'
    model=json.loads(modelpath.read_text());tasks,core=prepare_tasks(model,out)
    if len(tasks)!=protocol['evaluation']['fixtures']:raise ValueError('Unexpected validation cohort')
    rows=[]
    with ProcessPoolExecutor(max_workers=args.workers)as pool:
        futures=[pool.submit(evaluate,t)for t in tasks]
        try:
            for i,f in enumerate(as_completed(futures)):
                rows.extend(f.result())
                if (i+1)%10==0:print('Physical timeline fixtures',i+1,'/',len(tasks),flush=True)
        except BaseException:
            for future in futures:future.cancel()
            pool.shutdown(wait=False,cancel_futures=True)
            raise
    scored=pd.DataFrame(rows).merge(core[['season','fixture_uuid','player_uuid','minutes','total_points']],
        on=['season','fixture_uuid','player_uuid'],validate='many_to_one',how='left')
    if scored.total_points.isna().any():raise ValueError('Missing actual labels')
    reference=pd.read_csv(ROOT/'analysis/results/separated-goal-head-v2-validation-20261023/predictions.csv.gz')
    reference=reference[reference.arm.eq('candidate')]
    baseline=scored[scored.arm.eq('baseline')]
    paired=baseline.merge(reference,on=['season','fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('','_saved'))
    error=float(abs(paired.xp-paired.xp_saved).max())
    if error!=0 or len(paired)!=len(reference):raise ValueError('Selected B historical baseline not exactly reproduced')
    metrics=[]
    for (season,arm),group in scored.groupby(['season','arm']):
        cohorts={'all':group,'played':group[group.minutes.gt(0)],
                 'outfield':group[~group.keeper],
                 'rotation':group[~group.keeper&group.baseline_p_start.between(.2,.85)],
                 'reserve':group[~group.keeper&group.baseline_p_start.lt(.2)]}
        for name,g in cohorts.items():
            if not len(g):continue
            x=g.xp-g.total_points;m=g.xmins-g.minutes
            metrics.append(dict(season=season,arm=arm,cohort=name,rows=len(g),
                xp_mae=float(abs(x).mean()),xp_bias=float(x.mean()),
                minute_mae=float(abs(m).mean()),minute_bias=float(m.mean()),
                p0_brier=float(((g.p0-g.minutes.eq(0))**2).mean()),
                p60_brier=float(((g.p60-g.minutes.ge(60))**2).mean()),
                p90_brier=float(((g.p90-g.minutes.eq(90))**2).mean())))
    metric=pd.DataFrame(metrics);gates=protocol['gates'];passed=True;checks=[]
    for season in ['2024-25','2025-26']:
        s=metric[metric.season.eq(season)]
        a=s[s.cohort.eq('all')].set_index('arm');b=a.loc['baseline'];c=a.loc['candidate']
        played=s[s.cohort.eq('played')].set_index('arm')
        delta=dict(season=season,minute_mae_delta=float(c.minute_mae-b.minute_mae),
            absolute_minute_bias_delta=float(abs(c.minute_bias)-abs(b.minute_bias)),
            all_xp_mae_delta=float(c.xp_mae-b.xp_mae),
            played_xp_mae_delta=float(played.loc['candidate','xp_mae']-played.loc['baseline','xp_mae']),
            absolute_xp_bias_delta=float(abs(c.xp_bias)-abs(b.xp_bias)))
        ok=(delta['minute_mae_delta']<=gates['max_minute_MAE_increase_each_season'] and
            delta['absolute_minute_bias_delta']<=gates['max_absolute_minute_bias_increase_each_season'] and
            delta['all_xp_mae_delta']<=gates['max_all_xP_MAE_increase_each_season'] and
            delta['played_xp_mae_delta']<=gates['max_played_xP_MAE_increase_each_season'] and
            delta['absolute_xp_bias_delta']<=gates['max_absolute_xP_bias_increase_each_season'])
        passed=passed and ok;checks.append(dict(**delta,passed=bool(ok)))
    scored.to_csv(out/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    metric.to_csv(out/'metrics.csv',index=False)
    decision=dict(passed=bool(passed),fixtures=len(tasks),baseline_max_xp_error=error,
        candidate_policy_activated=False,production_changed=False,independent_certification=False,
        checks=checks,model_sha256=hashlib.sha256(modelpath.read_bytes()).hexdigest())
    (out/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    print(metric.to_string(index=False));print(json.dumps(decision,indent=2))


if __name__=='__main__':main()
