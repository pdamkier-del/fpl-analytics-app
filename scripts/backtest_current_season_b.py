"""Retrospective B replay of verified predeadline input capsules, never live forecasts.

No clock monkeypatch, source backdating, live guards disabled or new model fit
policy. Unavailable origins remain explicitly blocked rather than use later PM
inputs. Fixed policies were selected later: this is a diagnostic backtest.
"""
from pathlib import Path
import argparse,hashlib,json,shutil
import pandas as pd
from mm_candidate_forecast import infer_B
from mm_locked_bridge import attach_mm
from gk_solo_role import load_policy,mark_horizon_absences
from gk_joint_bridge import observations
from joint_role_bridge import load_assignment_policy
from nonpenalty_goal_bridge import load as load_goal,calculate
from fpl_v1_1_model.experimental_role_assignment_history import AssignmentHistory
from run_joint_gk_preview import run
from run_live_vfinal_joint_simulation import POINT_COMPONENTS
ROOT=Path(__file__).resolve().parents[1]
BASE=Path('data_v1_1/derived/live_locked_inputs/2026-27-v1')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def probability(value):
    if not -1e-12<=value<=1+1e-12:raise ValueError('Probability exceeds floating-point tolerance')
    return min(1.,max(0.,float(value)))

def verify_origin(inputs,source):
    inputs,source=Path(inputs),Path(source)
    prov=json.loads((inputs/'provenance.json').read_text());cut=pd.Timestamp(prov['data_at']);deadline=pd.Timestamp(prov['origin_deadline'])
    if cut>=deadline:raise ValueError('Replay cutoff is not predeadline')
    boot=json.loads((inputs/'bootstrap.json').read_text());fx=json.loads((inputs/'fixtures.json').read_text());pm=pd.read_csv(inputs/'pm.csv.gz',low_memory=False)
    origin=int(pm.gw.min());event=next(e for e in boot['events']if e['id']==origin)
    if pd.Timestamp(event['deadline_time'])!=deadline:raise ValueError('Official archived deadline mismatch')
    for name,doc in [('bootstrap',boot),('fixtures',fx)]:
        actual=hashlib.sha256(json.dumps(doc,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        if actual!=prov[name+'_sha256']or pd.Timestamp(prov[name+'_observed_at'])>=cut:raise ValueError('Archived source clock/hash mismatch')
    if not pd.to_datetime(pm.cutoff,utc=True).eq(cut).all():raise ValueError('PM cutoff mismatch')
    for col in ['y','minutes','started','actual_start','actual_minutes','total_points']:
        if col in pm and pm[col].notna().any():raise ValueError('Target outcomes in PM capsule: '+col)
    for name in ['player_fixture_observations','verified_penalty_attempts','verified_penalty_team_sides']:
        h=pd.read_csv(source/BASE/(name+'.csv.gz'),low_memory=False)
        if len(h)and not pd.to_datetime(h.available_at,utc=True).lt(cut).all():raise ValueError('Future PM history in '+name)
    if any(f.get('started')or pd.Timestamp(f['kickoff_time'])<=cut for f in fx if f.get('event')==origin):raise ValueError('Started target fixture in archived schedule')
    official={p['id']:p for p in boot['elements']if p['element_type']!=5}
    for _,g in pm[pm.gw.eq(origin)].groupby('fixture_uuid'):
        for tid,team in g.groupby('team_id'):
            if set(map(int,team.fpl_element))!={pid for pid,p in official.items()if p['team']==tid}:raise ValueError('Incomplete archived roster')
    return prov,boot,pm,origin

def replay(inputs,source,out,*,draws=400):
    inputs,source,out=map(Path,[inputs,source,out]);out.mkdir(parents=True,exist_ok=True)
    prov,boot,pm,origin=verify_origin(inputs,source)
    h=pd.read_csv(inputs/'history.csv.gz',low_memory=False);target=pd.read_csv(inputs/'target.csv.gz',low_memory=False)
    pred,_=infer_B(h,target,prov);pred=mark_horizon_absences(pred,boot)
    joined=attach_mm(pm,pred);offsets={fx:i for i,fx in enumerate(sorted(joined.fixture_uuid.unique()))};joined=joined[joined.gw.eq(origin)].copy();pred=pred[pred.gw.eq(origin)].copy()
    catalogue={r.player_uuid:next(p for p in boot['elements']if p['id']==int(r.fpl_element))for r in joined.itertuples()}
    role=load_assignment_policy(ROOT,ROOT/'analysis/results/joint-role-candidate-20261022/policy.json')
    assignment=AssignmentHistory(pd.read_csv(inputs/'roles.csv.gz',low_memory=False))
    model,_=load_goal(ROOT,ROOT/'analysis/results/nonpenalty-goal-head-20261023/policy.json')
    weights,goal_audit,goal_receipt=calculate(ROOT,joined,model,source_root=source)
    xp,moments,audit,_=run(joined,pred,observations(source),season='2026-27',draws=draws,
        role_policy=load_policy(source,h),chain=True,catalogue=catalogue,assignment_history=assignment,assignment_strength=role['strength'],
        ordinary_goal_weights=weights,conditional_penalties=True,physical_minutes=True,distributions=True,offsets=offsets)
    identity=joined.set_index(['fixture_uuid','player_uuid']);rows=[]
    for r in xp.itertuples():
        if abs(sum(getattr(r,k)for k in POINT_COMPONENTS)-r.xpts_fixture)>1e-8:raise ValueError('Point components do not reconcile')
        key=(r.fixture_uuid,r.player_uuid)
        if key not in moments:continue
        d=moments[key];person=identity.loc[key]
        rows.append(dict(gw=origin,fixture_uuid=r.fixture_uuid,player_uuid=r.player_uuid,player_id=int(person.fpl_element),fpl_code=int(catalogue[r.player_uuid]['code']),team_id=int(person.team_id),position={'GK':1,'GKP':1,'DEF':2,'MID':3,'FWD':4}[person.pos],kickoff=person.target_kickoff,p_start=probability(d['p']),expected_minutes=d['x'],pm_expected_minutes=d['x'],pm_sampled_minutes=r.expected_minutes if hasattr(r,'expected_minutes')else None,p_play=probability(d['p_play']),p60=probability(d['p60']),p90=probability(d['p90']),xp=r.xpts_fixture))
    result=dict(schema='B-current-season-backtest-v1',scope='retrospective_fixed_B_policy_not_original_forecast_not_independent_holdout',season='2026-27',gw=origin,cutoff=prov['data_at'],origin_deadline=prov['origin_deadline'],bootstrap_observed_at=prov['bootstrap_observed_at'],fixtures_observed_at=prov['fixtures_observed_at'],model_source='03d5c4d4777b44bc1d37884a1cf4dde106b45cab',goal_head_sources=goal_receipt['source_sha256'],generated_at=pd.Timestamp.now(tz='UTC').isoformat(),draws=draws,players=rows,source_hashes={n:digest(inputs/n)for n in ['target.csv.gz','history.csv.gz','pm.csv.gz','provenance.json','bootstrap.json','fixtures.json','roles.csv.gz']},code_hashes={str(p.relative_to(ROOT)):digest(p)for p in [ROOT/'scripts/run_joint_gk_preview.py',ROOT/'scripts/mm_candidate_forecast.py',ROOT/'scripts/b_chain_contract.py',ROOT/'src/fpl_v1_1_model/experimental_physical_timeline.py']},notes=['Model choices were selected later: reused diagnostic, not independent prospective accuracy.','Historical postmatch availability uses documented kickoff+3/4h proxies.','Only the origin GW is scored; no target outcomes enter inference. Seeds retain the original six-GW fixture offsets.','Physical normal-match timeline, five substitutions and 90-minute goalkeeper coverage are retained.','MM and PM expectations use the same analytic law; finite-Monte-Carlo sample minutes may differ.'])
    (out/'forecast.json').write_text(json.dumps(result,sort_keys=True,allow_nan=False)+'\n');(out/'audit.json').write_text(json.dumps(audit,sort_keys=True,allow_nan=False)+'\n')
    print('BACKTEST',origin,len(rows),'rows',flush=True);return result

def warmup_status(gw,minimum):
    prior=gw-1
    return dict(gw=gw,status='unsupported_model_warmup'if prior<minimum else'pending_backtest',
        minimum_prior_team_matches=minimum,maximum_prior_league_matches_per_team=prior,
        reason='Den uændrede målmands-/redningsmodel kræver mindst '+str(minimum)+' tidligere ligakampe pr. hold. Der bruges ingen senere kampe som opvarmning.'if prior<minimum else None)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--draws',type=int,default=400);a=p.parse_args();replay(a.inputs,a.source,a.out,draws=a.draws)
