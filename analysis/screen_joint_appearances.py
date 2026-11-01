"""Frozen partial substitution-budget experiment and signed minute diagnosis.

No publisher imports this script. Exact selected-B replay is mandatory.
"""
import argparse
import copy
import gzip
import hashlib
import json
import sqlite3
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd
from b_chain_contract import field_marginals
from gk_joint_bridge import marginals
from test_separated_goal_head import prepare_tasks, decode, UNKNOWN
from fpl_v1_1_model.experimental_joint_role_assignment import role_lineup_sampler
from fpl_v1_1_model.experimental_joint_appearances import AppearanceKernel, appearance_sampler
from fpl_v1_1_model.joint_simulator import simulate_many

ROOT = Path(__file__).resolve().parents[1]
KEY = ['season', 'fixture_uuid', 'player_uuid']


def minute_terms(p, q, s, c, started, minutes):
    """Signed terms add exactly to xM-observed; absolute terms do not add MAE."""
    cameo = (1-started) * (minutes > 0)
    return ((p-started)*s, started*(s-minutes),
            ((1-p)*q-cameo)*c, cameo*(c-minutes))


def evaluate(task):
    season, fx, seed, data, dist, factors, _ = task
    original = decode(copy.deepcopy(data))
    inp = replace(original, experimental_conditional_penalties=True,
        players=tuple(replace(p, goal_weight=factors[p.player_id], penalty_fallback_weight=p.goal_weight)
                      for p in original.players))
    kernel = AppearanceKernel(inp, dist)
    rows = []
    for arm in ['baseline', 'candidate']:
        effective = inp if arm == 'baseline' else replace(inp, players=tuple(
            replace(p, p_cameo_given_bench=kernel.moments[p.player_id]['q'])
            if not p.is_keeper else p for p in inp.players))
        mass = {p.player_id: field_marginals(p) for p in effective.players if not p.is_keeper}
        for team in (inp.home_team, inp.away_team):
            mass.update(marginals([p for p in inp.players if p.team == team and p.is_keeper]))
        scope = role_lineup_sampler(dist) if arm == 'baseline' else appearance_sampler(kernel)
        with scope:
            sim = simulate_many(inp, n=400, seed=seed)
        for p in effective.players:
            if p.player_id.startswith(UNKNOWN): continue
            m = mass[p.player_id]
            rows.append(dict(season=season, fixture_uuid=fx, player_uuid=p.player_id,
                team_id=p.team, arm=arm, keeper=p.is_keeper, p=p.p_start,
                q=p.p_cameo_given_bench, s=p.start_minutes_mean, c=p.cameo_minutes_mean,
                xp=sim[p.player_id]['xPts'], simulated_minutes=sim[p.player_id]['expected_minutes'],
                xmins=float(m@np.arange(91)), p0=float(m[0]),
                p60=float(m[60:].sum()), p90=float(m[90])))
    return rows, [dict(season=season, fixture_uuid=fx, **d) for d in kernel.diagnostics]


def summarize(scored, out):
    metrics = []
    for (season, arm), g in scored.groupby(['season', 'arm']):
        for name, v in {'all':g, 'played':g[g.minutes.gt(0)],
                        'rotation':g[~g.keeper & g.p.between(.2,.85)],
                        'keeper':g[g.keeper]}.items():
            if v.empty: continue
            metrics.append(dict(season=season, arm=arm, cohort=name, rows=len(v),
                minute_mae=float(abs(v.xmins-v.minutes).mean()),
                minute_bias=float((v.xmins-v.minutes).mean()),
                start_brier=float(((v.p-v.started)**2).mean()),
                p0_brier=float(((v.p0-v.minutes.eq(0))**2).mean()),
                p60_brier=float(((v.p60-v.minutes.ge(60))**2).mean()),
                p90_brier=float(((v.p90-v.minutes.eq(90))**2).mean()),
                xp_mae=float(abs(v.xp-v.total_points).mean()),
                xp_bias=float((v.xp-v.total_points).mean())))
    metrics = pd.DataFrame(metrics)
    metrics.to_csv(out/'metrics.csv', index=False)
    names = ['start_selection', 'starter_duration', 'cameo_selection', 'cameo_duration']
    diagnosis = []
    base = scored[scored.arm.eq('baseline')].copy()
    for season, g in base.groupby('season'):
        for cohort, v in {'all':g, 'actual_starters':g[g.started.eq(1)],
                          'actual_cameos':g[g.started.eq(0)&g.minutes.gt(0)],
                          'unused':g[g.minutes.eq(0)]}.items():
            if v.empty: continue
            terms = np.array([minute_terms(r.p,r.q,r.s,r.c,r.started,r.minutes) for r in v.itertuples()])
            if not np.allclose(terms.sum(axis=1), v.xmins-v.minutes, atol=1e-8, rtol=0):
                # Goalkeeper q is a conditional replacement weight, NOT a cameo
                # probability; its special normalized process is diagnosed separately.
                if not v.keeper.any(): raise AssertionError('Minute decomposition failed')
            field = v[~v.keeper]
            t = np.array([minute_terms(r.p,r.q,r.s,r.c,r.started,r.minutes) for r in field.itertuples()])
            if len(field):
                assert np.allclose(t.sum(axis=1), field.xmins-field.minutes, atol=1e-8, rtol=0)
                for j, name in enumerate(names):
                    diagnosis.append(dict(season=season, cohort=cohort, component=name, rows=len(field),
                        mean_signed_minutes=float(t[:,j].mean()),
                        mean_absolute_component=float(abs(t[:,j]).mean()),
                        scope='Outfield only. Absolute components are not additive MAE shares.'))
    pd.DataFrame(diagnosis).to_csv(out/'minute-error-components.csv', index=False)
    return metrics


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=2);args=ap.parse_args()
    out=args.out;protocol=json.loads((out/'protocol.json').read_text())
    model=json.loads((ROOT/'analysis/results/nonpenalty-goal-head-20261023/final-v2/model.json').read_text())
    tasks, core=prepare_tasks(model,out)
    labels=core[KEY+['minutes','started','total_points']]
    if labels.duplicated(KEY).any(): raise ValueError('Duplicate labels')
    if len(tasks)!=protocol['fixtures']: raise ValueError('Cohort changed')
    rows=[];diagnostics=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(evaluate,t) for t in tasks])):
            r,d=f.result();rows.extend(r);diagnostics.extend(d)
            if (i+1)%20==0: print('Joint appearance fixtures',i+1,'/',len(tasks),flush=True)
    scored=pd.DataFrame(rows).merge(labels,on=KEY,validate='many_to_one',how='left')
    if scored[['minutes','started','total_points']].isna().any().any(): raise ValueError('Missing labels')
    ref=pd.read_csv(ROOT/'analysis/results/separated-goal-head-v2-validation-20261023/predictions.csv.gz')
    ref=ref[ref.arm.eq('candidate')]
    paired=scored[scored.arm.eq('baseline')].merge(ref,on=KEY,validate='one_to_one',suffixes=('','_saved'))
    error=float(abs(paired.xp-paired.xp_saved).max())
    if error!=0 or len(paired)!=len(ref): raise ValueError(f'Exact B baseline failed: {error}')
    scored.to_csv(out/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pd.DataFrame(diagnostics).to_csv(out/'conditional-feasibility.csv',index=False)
    metrics=summarize(scored,out);checks=[]
    for season in sorted(scored.season.unique()):
        m=metrics[metrics.season.eq(season)&metrics.cohort.eq('all')].set_index('arm')
        b,c=m.loc['baseline'],m.loc['candidate']
        check=dict(season=season, minute_mae_delta=float(c.minute_mae-b.minute_mae),
            absolute_minute_bias_delta=float(abs(c.minute_bias)-abs(b.minute_bias)),
            xp_mae_delta=float(c.xp_mae-b.xp_mae),
            absolute_xp_bias_delta=float(abs(c.xp_bias)-abs(b.xp_bias)))
        check['passed']=bool(check['minute_mae_delta']<=.05 and check['absolute_minute_bias_delta']<=.25
                             and check['xp_mae_delta']<=.005 and check['absolute_xp_bias_delta']<=.02)
        checks.append(check)
    with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True) as db:
        clock=db.execute("SELECT count(*),sum(sub_on_second is not null),sum(sub_off_second is not null) FROM player_fixture_observations WHERE is_final=1 AND season IN ('2024-25','2025-26')").fetchone()
    decision=dict(fixtures=len(tasks),player_rows=len(scored)//2,baseline_max_xp_error=error,
        numerical_gate_passed=all(c['passed'] for c in checks),checks=checks,
        historical_clock_coverage=dict(rows=clock[0],sub_on_second=clock[1],sub_off_second=clock[2]),
        activated=False,publishable=False,production_changed=False,independent_validation=False,
        reason='Partial appearance-budget coupling only; no paired exits or validated physical-to-FPL clock. Reused periods and 400 draws do not establish a new calibrated full chain.',
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        protocol_sha256=hashlib.sha256((out/'protocol.json').read_bytes()).hexdigest())
    (out/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    print(metrics.to_string(index=False));print(json.dumps(decision,indent=2))


if __name__=='__main__':main()
