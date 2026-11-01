"""Archived six-GW B-chain rehearsal; never writes an app or manager state."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import joint_role_bridge
import run_joint_gk_preview as bridge
from mm_candidate_forecast import infer_B
from mm_locked_bridge import attach_mm
from gk_solo_role import SoloRolePolicy, mark_horizon_absences
from gk_joint_bridge import observations
from fpl_v1_1_model.experimental_role_assignment_history import AssignmentHistory
from fpl_v1_1_model.experimental_joint_appearances import AppearanceKernel, appearance_sampler
from fpl_v1_1_model import joint_simulator as simulator


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--artifact',type=Path,required=True)
    ap.add_argument('--forecast',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();root=Path(__file__).resolve().parents[1];src=args.artifact
    inputs=src/'work/current-B-inputs';out=args.out;out.mkdir(parents=True,exist_ok=True)
    h=pd.read_csv(inputs/'history.csv.gz',low_memory=False)
    t=pd.read_csv(inputs/'target.csv.gz',low_memory=False)
    pm=pd.read_csv(inputs/'pm.csv.gz',low_memory=False)
    provenance=json.loads((inputs/'provenance.json').read_text())
    bootstrap=json.loads((inputs/'bootstrap.json').read_text())
    reference=json.loads(args.forecast.read_text())
    reference_fixtures={(f['fixture_uuid'],p['player_uuid']):f
        for p in reference['players'] for w in p['weeks'] for f in w['fixtures']}
    pred,_=infer_B(h,t,provenance);pred=mark_horizon_absences(pred,bootstrap)
    joined=attach_mm(pm,pred)
    catalogue={r.player_uuid:{p['id']:p for p in bootstrap['elements']}[int(r.fpl_element)] for r in joined.itertuples()}
    squads=pd.read_csv(src/'work/joint-gk-current/role-squad-evidence.csv.gz')
    for clock in ['clock','kick']:
        squads[clock]=pd.to_datetime(squads[clock],utc=True,format='mixed')
    policy=SoloRolePolicy(h,squads)
    weights=pd.read_csv(src/'work/joint-gk-current/nonpenalty-goal-head.csv.gz')
    weights={(r.fixture_uuid,r.player_uuid):r.ordinary_goal_weight for r in weights.itertuples()}
    evidence=json.loads((src/'work/gk-official-evidence/evidence.json').read_text())
    incomplete=(evidence['team_id'],) if evidence['unlisted_competitors'] else ()
    # Historical Core stays fixed. For the live season use the exact origin
    # archive, never a different local capture with a matching directory name.
    obs=observations(root);obs=obs[~obs.season.eq('2026-27')]
    live_path=src/'data_v1_1/derived/live_locked_inputs/2026-27-v1/player_fixture_observations.csv.gz'
    live=pd.read_csv(live_path,low_memory=False)
    live=live[live.fpl_position.isin(['GK','GKP','G'])].copy()
    live['known_at']=pd.to_datetime(live.available_at,utc=True)
    if 'season' not in live:live['season']='2026-27'
    obs=pd.concat([obs,live[obs.columns]],ignore_index=True).drop_duplicates(['season','fixture_uuid','player_uuid'])
    state={};rows=[];checks=[];feasibility=[]
    original_assignment=joint_role_bridge.apply_assignment
    original_export=bridge.simulate_with_distributions
    raw_match=simulator.simulate_match
    def assignment(frame,*a,**kw):
        result=original_assignment(frame,*a,**kw)
        state['fixture']=frame.fixture_uuid.iloc[0];state['roles']=result[1]
        return result
    def export(inp,*,n,seed,include_samples):
        baseline=original_export(inp,n=n,seed=seed,include_samples=include_samples)
        kernel=AppearanceKernel(inp,state['roles']);fx=state['fixture']
        if not checks:
            diagnostic=[]
            for p in inp.players:
                ref=reference_fixtures.get((fx,p.player_id))
                if ref is not None:
                    diagnostic.append(dict(player=p.player_id,p_delta=p.p_start-ref['p_start'],
                        xp_delta=baseline[p.player_id]['xPts']-ref['xpts']))
            print('First fixture baseline diagnostic',seed,json.dumps(diagnostic),flush=True)
        feasibility.extend(dict(fixture_uuid=fx,**d) for d in kernel.diagnostics)
        # The caller is inside the baseline role hook. Candidate supplies that
        # same mixture itself, so temporarily use the unwrapped simulator.
        outer=simulator.simulate_match
        try:
            simulator.simulate_match=raw_match
            with appearance_sampler(kernel):
                candidate=original_export(inp,n=n,seed=seed,include_samples=include_samples)
        finally:
            simulator.simulate_match=outer
        for team in (inp.home_team,inp.away_team):
            ps=[p for p in inp.players if p.team==team]
            mins=np.array([candidate[p.player_id]['scenarios']['minutes'] for p in ps])
            keep=np.array([p.is_keeper for p in ps])
            if not (mins[keep].sum(axis=0)==90).all() or (mins>0).sum(axis=0).max()>16:
                raise AssertionError('Shared appearance/GK scenario contract failed')
        for p in inp.players:
            if p.player_id.startswith('__unlisted_goalkeeper__:'):continue
            b,c=baseline[p.player_id],candidate[p.player_id]
            points=np.asarray(c['scenarios']['points'])
            if len(points)!=n or abs(points.mean()-c['xPts'])>1e-9:
                raise AssertionError('TS scenario mean differs from PM')
            rows.append(dict(fixture_uuid=fx,player_uuid=p.player_id,
                baseline_xp=b['xPts'],candidate_xp=c['xPts'],
                baseline_xmins=p.p_start*p.start_minutes_mean+(1-p.p_start)*p.p_cameo_given_bench*p.cameo_minutes_mean if not p.is_keeper else np.nan,
                candidate_xmins=kernel.moments[p.player_id]['x'] if not p.is_keeper else np.nan))
        checks.append(dict(fixture_uuid=fx,players=len(inp.players),draws=n,
                           shared_appearance_limit_passed=True,gk_90_passed=True,ts_scenario_mean_passed=True))
        return baseline
    try:
        joint_role_bridge.apply_assignment=assignment;bridge.simulate_with_distributions=export
        baseline,details,_,_=bridge.run(joined,pred,obs,season='2026-27',
            incomplete_teams=incomplete,role_policy=policy,distributions=True,chain=True,
            catalogue=catalogue,assignment_history=AssignmentHistory(pd.read_csv(inputs/'roles.csv.gz')),
            assignment_strength=.5,ordinary_goal_weights=weights,conditional_penalties=True)
    finally:
        joint_role_bridge.apply_assignment=original_assignment;bridge.simulate_with_distributions=original_export
    ref=pd.DataFrame([dict(fixture_uuid=f['fixture_uuid'],player_uuid=p['player_uuid'],xp=f['xpts'])
        for p in reference['players'] for w in p['weeks'] for f in w['fixtures']])
    matched=baseline.merge(ref,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    matched.drop(columns=['distribution','scenarios'],errors='ignore').to_csv(out/'archived-baseline-replay.csv',index=False)
    error=float(abs(matched.xpts_fixture-matched.xp).max())
    if len(matched)!=len(ref) or error!=0:raise ValueError(f'Archived current baseline mismatch: {error}')
    results=pd.DataFrame(rows);results.to_csv(out/'current-comparison.csv',index=False)
    pd.DataFrame(feasibility).to_csv(out/'current-feasibility.csv',index=False)
    receipt=dict(scope='Archived 24 October six-GW inputs; not a fresh forecast or full TS optimizer test',
        source_asof=provenance['data_at'],fixtures=len(checks),players=int(results.player_uuid.nunique()),
        rows=len(results),gws=sorted(t.gw.unique().tolist()),baseline_max_xp_error=error,
        max_abs_outfield_xmins_change=float(abs(results.candidate_xmins-results.baseline_xmins).max()),
        contracts=checks,activated=False,physical_timeline_certified=False,production_changed=False,
        input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [inputs/'history.csv.gz',inputs/'target.csv.gz',inputs/'pm.csv.gz',inputs/'roles.csv.gz',args.forecast,live_path]})
    (out/'current-six-GW.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='contracts'},indent=2))


if __name__=='__main__':main()
