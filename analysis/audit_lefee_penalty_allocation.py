"""Read-only causal input ablation; never a fitted/published replacement model."""
import sys,json,pathlib,hashlib,argparse
from dataclasses import replace
import numpy as np,pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import run_joint_gk_preview as runner
from fpl_v1_1_model import joint_simulator as sim
from fpl_v1_1_model.experimental_role_assignment_history import AssignmentHistory
from fpl_v1_1_model.deadline_components import weighted_totals
from fpl_v1_1_model.attack import shrunk_rate_per90
from mm_candidate_forecast import infer_B
from mm_locked_bridge import attach_mm
from gk_solo_role import mark_horizon_absences,load_policy
parser=argparse.ArgumentParser();parser.add_argument('--inputs',type=pathlib.Path,required=True);parser.add_argument('--forecast',type=pathlib.Path,required=True);parser.add_argument('--out',type=pathlib.Path,required=True);args=parser.parse_args()
root=ROOT;inputs=args.inputs;forecast=json.loads(args.forecast.read_text())
uid='40b6a84e-8e7e-529b-8b4e-a2979b1bc8e4';player=next(p for p in forecast['players']if p['player_uuid']==uid);fixture=player['weeks'][0]['fixtures'][0];fx=fixture['fixture_uuid']
shots_by_gw={};source=[]
for path in pathlib.Path('data_v1_1/raw/live-captures/20261018T190738Z/fotmob/details').glob('*.json'):
 d=json.loads(path.read_text());g=d.get('general',{})
 if g.get('leagueId')!=47 or 8472 not in [g.get('homeTeam',{}).get('id'),g.get('awayTeam',{}).get('id')]:continue
 gw=int(g['matchRound'])
 if gw>7:continue
 assert g.get('finished') is True and isinstance(d['content'].get('shotmap'),dict) and 'shots'in d['content']['shotmap']
 selected=[s for s in d['content']['shotmap']['shots']if s.get('playerId')==1049999]
 assert all(s.get('expectedGoals')is not None and float(s['expectedGoals'])>=0 for s in selected)
 shots={str(s['id']):s for s in selected};assert len(shots)==len(selected) and gw not in shots_by_gw
 xg=sum(s.get('expectedGoals',0)or 0 for s in shots.values());pxg=sum(s.get('expectedGoals',0)or 0 for s in shots.values()if s.get('situation')=='Penalty')
 shots_by_gw[gw]={'gw':gw,'xg':xg,'penalty_xg':pxg,'npxg':xg-pxg,'shots':len(shots),'penalty_shots':sum(s.get('situation')=='Penalty'for s in shots.values())};source.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
assert set(shots_by_gw)==set(range(1,8))
# Preserve the original FPL per-match xG scale: only remove the same-provider
# fraction attributable to verified penalty shots. This is an input ablation,
# not a claimed exact replacement npxG feed or a refitted population prior.
hist=pd.read_csv('data_v1_1/derived/live_locked_inputs/2026-27-v1/player_fixture_observations.csv.gz',low_memory=False);ph=hist[hist.player_uuid.eq(uid)].sort_values('kickoff_at').copy();assert set(ph.gw)==set(range(1,8))
ph['ablation_xg']=[float(r.xg)*(shots_by_gw[int(r.gw)]['npxg']/shots_by_gw[int(r.gw)]['xg'])if shots_by_gw[int(r.gw)]['xg']else float(r.xg)for r in ph.itertuples()]
params=json.load(open('analysis/results/joint-component-recovery-v1/player_attack_fit.json'))['goal']
num,den=weighted_totals(ph,'ablation_xg',params['recency_half_life']);oldnum,_=weighted_totals(ph,'xg',params['recency_half_life'])
pm=pd.read_csv(inputs/'pm.csv.gz',low_memory=False);le=pm[pm.player_uuid.eq(uid)&pm.fixture_uuid.eq(fx)].iloc[0];prior=float(le.goal_role_prior90)
oldrate=shrunk_rate_per90(oldnum,den,prior,params['current_season_position_prior_minutes_tau']);newrate=shrunk_rate_per90(num,den,prior,params['current_season_position_prior_minutes_tau']);assert abs(oldrate-float(le.goal_rate90))<1e-10,(oldrate,le.goal_rate90)
factor=newrate/oldrate
h=pd.read_csv(inputs/'history.csv.gz',low_memory=False);t=pd.read_csv(inputs/'target.csv.gz',low_memory=False);prov=json.load(open(inputs/'provenance.json'));bootstrap=json.load(open(inputs/'bootstrap.json'));pred,_=infer_B(h,t,prov);pred=mark_horizon_absences(pred,bootstrap);joined=attach_mm(pm,pred);offsets={f:i for i,f in enumerate(sorted(joined.fixture_uuid.unique()))};chosen=joined[joined.fixture_uuid.eq(fx)]
policy=load_policy(root,h);catalogue={r.player_uuid:next(p for p in bootstrap['elements']if p['id']==int(r.fpl_element))for r in chosen.itertuples()}
base_sim=sim.simulate_many;report={};captured=[]
def sample(inp,n,seed):
 events=[];match_current=sim.simulate_match
 def traced(inp,rng,**kwargs):
  res=match_current(inp,rng,**kwargs);r=res[uid];events.append([r.points,r.goals-r.penalty_goals,r.penalty_goals,r.minutes,r.bonus,sum(v.goals for pid,v in res.items()if next(p for p in inp.players if p.player_id==pid).team==next(p for p in inp.players if p.player_id==uid).team)]);return res
 sim.simulate_match=traced
 try:result=base_sim(inp,n=n,seed=seed)
 finally:sim.simulate_match=match_current
 a=np.array(events,float);captured.append(a)
 return result,{'xp':float(a[:,0].mean()),'xp_mc_standard_error':float(a[:,0].std(ddof=1)/np.sqrt(n)),'ordinary_goals':float(a[:,1].mean()),'penalty_goals':float(a[:,2].mean()),'simulated_minutes':float(a[:,3].mean()),'bonus':float(a[:,4].mean())}
def intercepted(inp,n,seed):
 changed=replace(inp,players=tuple(replace(p,goal_weight=p.goal_weight*factor)if p.player_id==uid else p for p in inp.players))
 baseline,info=sample(inp,n,seed);report['published_seed_control']=info;report['published_seed_shadow']=sample(changed,n,seed)[1]
 assert info['xp']==fixture['xpts'],('Baseline did not reproduce public xP',info,fixture['xpts'])
 print('Exact published 400-draw baseline reproduced',flush=True)
 report['longer_baseline']=sample(inp,4000,792681)[1];print('Longer baseline complete',flush=True);report['longer_shadow']=sample(changed,4000,792681)[1]
 left,right=captured[-2:];delta=right[:,0]-left[:,0]
 report['paired_simulation_mean_delta']=float(delta.mean());report['paired_simulation_mc_standard_error']=float(delta.std(ddof=1)/np.sqrt(len(delta)))
 report['same_realized_minutes_penalties_and_team_goals']=bool(np.array_equal(left[:,[2,3,5]],right[:,[2,3,5]]))
 assert report['same_realized_minutes_penalties_and_team_goals']
 report['input_invariants']={'same_minutes_and_starts':all((a.p_start,a.p_cameo_given_bench,a.start_minutes_mean,a.cameo_minutes_mean)==(b.p_start,b.p_cameo_given_bench,b.start_minutes_mean,b.cameo_minutes_mean)for a,b in zip(inp.players,changed.players)),'same_team_goal_intensities':(inp.lambda_home_goals,inp.lambda_away_goals)==(changed.lambda_home_goals,changed.lambda_away_goals),'same_penalty_process':all((a.penalty_weight,a.penalty_conversion,a.penalty_order)==(b.penalty_weight,b.penalty_conversion,b.penalty_order)for a,b in zip(inp.players,changed.players)),'only_one_ordinary_goal_weight_changed':sum(a!=b for a,b in zip(inp.players,changed.players))==1}
 return baseline
runner.simulate_many=intercepted
runner.run(chosen,pred[pred.fixture_uuid.eq(fx)],runner.observations(root),season='2026-27',draws=400,incomplete_teams=(forecast['official_gk_evidence']['team_id'],),offsets=offsets,role_policy=policy,chain=True,catalogue=catalogue,assignment_history=AssignmentHistory(pd.read_csv(inputs/'roles.csv.gz')),assignment_strength=.5)
report.update(scope='READ_ONLY_SINGLE_PLAYER_INPUT_ABLATION_NOT_A_VALIDATED_MODEL_CANDIDATE',forecast_sha256=forecast['forecast_sha256'],fixture_uuid=fx,player=player['name'],shots=list(sorted(shots_by_gw.values(),key=lambda r:r['gw'])),shot_sources=source,fpl_total_xg=float(ph.xg.sum()),fpl_total_xa=float(ph.xa.sum()),role_prior90=prior,old_goal_rate90=oldrate,shadow_goal_rate90=newrate,ordinary_goal_weight_factor=factor,role_prior_frozen_inclusive=True,production_or_preview_changed=False,not_an_estimate_of_historical_prediction_improvement=True)
args.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k not in ['shot_sources','shots']},indent=2))
