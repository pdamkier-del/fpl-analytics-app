#!/usr/bin/env python3
"""Real historical B -> unchanged PM replay; no invented six-GW TS history."""
from pathlib import Path
import argparse,hashlib,json,gzip
import pandas as pd
import numpy as np
from individual_mm_evidence import load_frame
from run_vfinal_integrated import build_final_frame,FROZEN,score
from fpl_v1_1_model.paired_joint import read_frozen_table
from mm_locked_bridge import simulate_pair,code_identity
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/mm-locked-chain-20261017'


def main():
    p=argparse.ArgumentParser();p.add_argument('--gws',nargs='+',type=int,default=list(range(22,39)));p.add_argument('--render-only',action='store_true');a=p.parse_args()
    pm=build_final_frame();pm=pm[pm.gw.isin(a.gws)].copy();pm['season']='2025-26'
    frozen=ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz'
    b=load_frame(frozen);b=b[b.season.eq('2025-26')&b['mode'].eq('B')&b.gw.isin(a.gws)]
    # PM has a smaller frozen roster. Keep complete PM fixtures, explicitly count
    # B players outside its universe; never imply full B coverage downstream.
    common=b.merge(pm[['fixture_uuid','player_uuid','pos']],on=['fixture_uuid','player_uuid'],validate='one_to_one')
    before=code_identity(ROOT)
    result=pd.read_csv(OUT/'paired_pm.csv.gz',float_precision='round_trip') if a.render_only else simulate_pair(pm,common,season='2025-26')
    if a.render_only and 'sampler_expected_minutes' not in result:
        from mm_locked_bridge import attach_mm,locked_sampler_expectation
        frames={'production_minutes':pm,'B_minutes':attach_mm(pm,common)}
        parts=[]
        for arm,g in result.groupby('arm',sort=False):
            inputs=frames[arm].set_index(['fixture_uuid','player_uuid']).reindex(pd.MultiIndex.from_frame(g[['fixture_uuid','player_uuid']]))
            g=g.copy();g['sampler_expected_minutes']=locked_sampler_expectation(inputs.v4_workload_start_p_start,inputs.v4_p_cameo_given_bench,inputs.v4_start_minutes_mean,inputs.v4_cameo_minutes_mean)
            parts.append(g)
        result=pd.concat(parts).sort_values(['fixture_uuid','arm','player_uuid'],key=lambda s:s.map({'production_minutes':0,'B_minutes':1}) if s.name=='arm' else s).reset_index(drop=True)
    expected=set(map(tuple,common[['fixture_uuid','player_uuid']].to_numpy()))
    if set(result.arm)!={'production_minutes','B_minutes'}:raise ValueError('Incomplete PM arms')
    for _,g in result.groupby('arm'):
        if len(g)!=len(expected) or set(map(tuple,g[['fixture_uuid','player_uuid']].to_numpy()))!=expected:
            raise ValueError('PM replay cohort changed')
    # Re-run one complete paired fixture with the identical seed/budget.
    first=sorted(pm.fixture_uuid.unique())[0]
    again=simulate_pair(pm[pm.fixture_uuid.eq(first)],common[common.fixture_uuid.eq(first)],season='2025-26')
    if set(result)!=set(again):raise ValueError('PM result schema changed')
    result=result[again.columns]
    pd.testing.assert_frame_equal(result[result.fixture_uuid.eq(first)].reset_index(drop=True),again,check_exact=True)
    if before!=code_identity(ROOT):raise ValueError('Locked code changed')
    OUT.mkdir(parents=True,exist_ok=True)
    result.to_csv(OUT/'paired_pm.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    # Compare outputs and components, without pretending Monte Carlo deltas are
    # estimates of predictive improvement on an untouched validation period.
    keys=['fixture_uuid','player_uuid','gw']
    wide=result[result.arm.eq('B_minutes')].merge(result[result.arm.eq('production_minutes')],on=keys,suffixes=('_B','_old'),validate='one_to_one')
    for c in ['xpts','xmins','p_start','simulated_minutes']:wide['delta_'+c]=wide[c+'_B']-wide[c+'_old']
    wide.to_csv(OUT/'paired_deltas.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    truth=read_frozen_table(FROZEN,'targets')
    evaluated=wide.merge(truth[['fixture_uuid','player_uuid','total_points']],on=['fixture_uuid','player_uuid'],validate='one_to_one')
    if len(evaluated)!=len(wide):raise ValueError('Historical point outcomes missing')
    point_metrics={arm:score(evaluated.total_points,evaluated['xpts_'+arm]) for arm in ['old','B']}
    # Paired four-GW circular blocks, fixed RNG; reused diagnostic data only.
    blocks=[]
    for gw,g in evaluated.groupby('gw',sort=True):
        eb=g.xpts_B-g.total_points;eo=g.xpts_old-g.total_points
        blocks.append([len(g),abs(eb).sum(),abs(eo).sum(),(eb*eb).sum(),(eo*eo).sum()])
    blocks=np.asarray(blocks);rng=np.random.default_rng(20261017);boot=[]
    for _ in range(1000):
        starts=rng.integers(len(blocks),size=int(np.ceil(len(blocks)/4)))
        indices=np.concatenate([(s+np.arange(4))%len(blocks) for s in starts])[:len(blocks)]
        n,ab,ao,sb,so=blocks[indices].sum(axis=0)
        boot.append([ab/n-ao/n,np.sqrt(sb/n)-np.sqrt(so/n)])
    ci={name:np.quantile(np.array(boot)[:,i],[.025,.975]).tolist() for i,name in enumerate(['mae','rmse'])}
    summary=dict(scope='historical_replay',season='2025-26',gws=sorted(a.gws),fixtures=int(pm.fixture_uuid.nunique()),
        matched_players=len(common),B_rows_outside_PM=int(len(b)-len(common)),draws=400,seed=93000000,first_fixture_exact_reproduction=True,
        locked_model_active=False,production_changed=False,PM_math_changed=False,TS_math_changed=False,
        MM_source_sha256=hashlib.sha256(frozen.read_bytes()).hexdigest(),locked_code_sha256=before,
        mean_delta={c:float(wide['delta_'+c].mean()) for c in ['xpts','xmins','p_start','simulated_minutes']},
        max_abs_delta_xpts=float(wide.delta_xpts.abs().max()),
        minute_sampler_mean_delta={arm:float((g.sampler_expected_minutes-g.xmins).mean()) for arm,g in result.groupby('arm')},
        minute_sampler_B_high_minutes_mean_delta=float((result.loc[result.arm.eq('B_minutes')&result.xmins.gt(60),'sampler_expected_minutes']-result.loc[result.arm.eq('B_minutes')&result.xmins.gt(60),'xmins']).mean()),
        minute_sampler_mean_matches_MM=False,
        diagnostic_xP_metrics=point_metrics,paired_delta_xP_interval95=ci,
        TS_status='Not Available: historical PM rows are single-GW forecasts at different origins, not six GWs known at one origin.',
        live_status='Not Available: current PR8 role/chance/return-duration feature bridge not verified.',
        certification='Reused research period; no independent validation. PMF remains separate experimental output; locked PM duration sampler unchanged.')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    named=pd.read_csv(ROOT/'analysis/results/mm-integration-preview-20261017/player_identity_names.csv').set_index('player_uuid').name.to_dict()
    clubs=pd.read_csv(ROOT/'analysis/results/individual-mm-refinement-20261016/club_metrics.csv')
    clubs=clubs[clubs.season.eq('2025-26')].drop_duplicates('team_id').set_index('team_id').club.to_dict()
    identity=pm.set_index(['fixture_uuid','player_uuid'])
    rows=[]
    for r in wide.to_dict('records'):
        source=identity.loc[(r['fixture_uuid'],r['player_uuid'])]
        r.update(name=named[r['player_uuid']],club=clubs[int(source.team_id)],cutoff=source.cutoff)
        rows.append(r)
    app=ROOT/'app/mm-preview';app.mkdir(parents=True,exist_ok=True)
    packed=gzip.compress(json.dumps(dict(summary=summary,players=rows),allow_nan=False,separators=(',',':')).encode(),mtime=0)
    (app/'pm-chain.json.gz').write_bytes(packed)
    (app/'pm-chain-index.json').write_text(json.dumps(dict(url='pm-chain.json.gz',sha256=hashlib.sha256(packed).hexdigest(),scope='historical_replay',rows=len(rows)))+'\n')
    (OUT/'manifest.json').write_text(json.dumps(dict(scope='historical_replay',input_MM=summary['MM_source_sha256'],
        locked_code_sha256=before,outputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='manifest.json'},
        app_payload_sha256=hashlib.sha256(packed).hexdigest()),indent=2)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
