#!/usr/bin/env python3
"""Reproducible forensic audit and opt-in PM sampler experiment; no publication."""
from pathlib import Path
import sys,json,hashlib,argparse
import numpy as np,pandas as pd
from scipy.special import ndtr
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.experimental_mean_preserving_minutes import clipped_rounded_mean,shadow_sampler
from run_live_vfinal_joint_simulation import simulate,POINT_COMPONENTS
from build_locked_live_v2_baseline import exact_frozen_duration_constants
B=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
W=ROOT/'work/live-final-model'
OUT=ROOT/'analysis/results/full-model-audit-20261012'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,data):OUT.mkdir(parents=True,exist_ok=True);(OUT/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--simulate',action='store_true');a=ap.parse_args()
 receipt=json.loads((ROOT/'model/checkpoints/current-diagnostic.json').read_text())
 names=['vfinal_live_full_simulator_input.csv.gz','live_vfinal_fixture_xp.csv.gz','player_fixture_observations.csv.gz','observed_team_xg_history.csv.gz','reconstructed_training_features.csv.gz']
 for name in names:
  p=B/name;rel=str(p.relative_to(ROOT));assert digest(p)==receipt['files'][rel],rel
 f=pd.read_csv(B/names[0],low_memory=False);xp=pd.read_csv(B/names[1]);history=pd.read_csv(B/names[2],low_memory=False);h=pd.read_csv(B/names[3]);training=pd.read_csv(B/names[4],low_memory=False)
 cutoff=pd.to_datetime(f.cutoff,utc=True);assert cutoff.nunique()==1;cut=cutoff.iloc[0]
 assert (pd.to_datetime(history.available_at,utc=True)<cut).all()
 assert (pd.to_datetime(training.outcome_known_at,utc=True)<cut).all()
 assert not f.duplicated(['fixture_uuid','player_uuid']).any()
 assert not history.duplicated(['fixture_uuid','player_uuid']).any()
 fixtures={int(r['id']):r for r in json.loads((W/'fixtures.json').read_text())}
 h=h.copy();goals=[]
 for r in h.itertuples():
  fx=fixtures[int(r.fixture_uuid.rsplit('-',1)[1])];side='h' if fx['team_h']==r.team_id else 'a' if fx['team_a']==r.team_id else None
  if side is None or fx['team_'+side+'_score'] is None:raise ValueError('Missing verified historical side/score')
  goals.append(fx['team_'+side+'_score'])
 h['official_goals']=goals
 sh=h.groupby('team_id').agg(games=('xg','size'),xg=('xg','sum'),goals=('official_goals','sum'))
 sh['tau50_factor']=(sh.goals+50)/(sh.xg+50)
 base_seconds=np.array([clipped_rounded_mean(v,10.) for v in f.v4_start_minutes_mean])
 cameo_seconds=np.array([clipped_rounded_mean(v,7.,1,45) for v in f.v4_cameo_minutes_mean])
 intended=f.v4_workload_start_xmins.to_numpy()
 actual=f.v4_workload_start_p_start.to_numpy()*base_seconds+(1-f.v4_workload_start_p_start.to_numpy())*f.v4_p_cameo_given_bench.to_numpy()*cameo_seconds
 focus={}
 for name in ['Haaland','Saka']:
  rows=f[f.player.eq(name)].sort_values('target_gw');pid=rows.player_uuid.iloc[0];observed=history[history.player_uuid.eq(pid)]
  joined=rows.merge(xp,on=['fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('_input','_sim'))
  records=[]
  for r in joined.to_dict('records'):
   components={c:float(r[c]) for c in POINT_COMPONENTS};assert np.isclose(sum(components.values()),r['xpts_fixture'])
   records.append(dict(gw=int(r['target_gw']),p_start=float(r['p_start']),mm_xmins=float(r['xmins']),conditional_start_minutes=float(r['start_minutes_mean']),simulated_minutes=float(r['expected_minutes_sim']),xp=float(r['xpts_fixture']),components=components,penalty_miss_subcomponent=float(r['penalty_miss_points']),goal_mu=float(r['goal_mu']),assist_mu=float(r['assist_mu'])))
  focus[name]=dict(fpl_id=int(rows.fpl_element.iloc[0]),observed_games=len(observed),starts=int(observed.started.sum()),minutes=float(observed.minutes.sum()),forecast=records)
 che=f[f.team_id.eq(6)].groupby(['target_gw','fixture_uuid']).first().reset_index()
 che['team_lambda']=np.where(che.home_team_id.eq(6),che.lambda_home_goals,che.lambda_away_goals)
 focus['Chelsea']=dict(sh.loc[6].to_dict(),forecast=[dict(gw=int(r.target_gw),original_lambda=float(r.team_lambda),tau50_shadow_lambda=float(r.team_lambda*sh.loc[6,'tau50_factor'])) for r in che.itertuples()])
 report=dict(classification='READ_ONLY_FULL_CHAIN_AUDIT',base_commit='2b1983a',source_cutoff=receipt['cutoff'],source_workflow=receipt['source_workflow'],input_checksums={n:digest(B/n) for n in names},locked_model_active=False,focus=focus,training_rows=len(training),training_gws=sorted(map(int,training.gw.unique())),baseline_duration_constants=exact_frozen_duration_constants(),structural_checks=dict(expected_starters_max_error=float((f.groupby(['fixture_uuid','team_id']).p_start.sum()-11).abs().max()),minute_mean_bias=float(np.mean(actual-intended)),worst_minute_mean_bias=float(np.min(actual-intended)),player_fixture_rows_with_cameo_mean_above_old_sampler_support=int(f.v4_cameo_minutes_mean.gt(45).sum()),independent_starts_not_exact_realized_xi=True),restrictions=['Historical availability uses documented kickoff proxies, not recovered publication clocks','2025/26 GW22-38 has been reused for previous model decisions','MM vNext is a shadow minute model, not the minute source of original PM/TS','2125-point benchmark reproduces its ledger but archived GW6-38 forecasts contain only current-GW targets, not a six-GW horizon'])
 write('audit.json',report);sh.reset_index().to_csv(OUT/'team_finishing_source.csv',index=False)
 print('AUDIT_FOCUS',json.dumps({k:{a:b for a,b in v.items() if a!='forecast'} for k,v in focus.items()}),flush=True)
 if a.simulate:
  seeds={fx:i for i,fx in enumerate(sorted(f.fixture_uuid.unique()))}
  original,oa=simulate(f,draws=400,fixture_seed_offsets=seeds)
  check=original.merge(xp,on=['fixture_uuid','player_uuid'],suffixes=('_rerun','_saved'),validate='one_to_one')
  cols=['xpts_fixture','expected_minutes',*POINT_COMPONENTS]
  if any(not np.allclose(check[c+'_rerun'],check[c+'_saved'],rtol=0,atol=1e-10) for c in cols):raise ValueError('Original baseline numerical reproduction failed')
  with shadow_sampler():candidate,ca=simulate(f,draws=400,fixture_seed_offsets=seeds)
  original.to_csv(OUT/'live_original_reproduced.csv.gz',index=False,compression='gzip');candidate.to_csv(OUT/'live_mean_preserved.csv.gz',index=False,compression='gzip')
  paired=original.merge(candidate,on=['fixture_uuid','player_uuid'],suffixes=('_original','_candidate'),validate='one_to_one').merge(f[['fixture_uuid','player_uuid','player','fpl_element','target_gw']],on=['fixture_uuid','player_uuid'],validate='one_to_one')
  paired.to_csv(OUT/'live_paired_sampler.csv.gz',index=False,compression='gzip')
  write('live_experiment.json',dict(classification='EXPERIMENTAL_SHADOW_NOT_PROMOTED',source_cutoff=receipt['cutoff'],original_reproduction_passed=True,locked_coefficients_untouched=True,promotion_allowed=False,draws=400,player_fixture_rows=len(paired),focus=paired[paired.player.isin(['Haaland','Saka'])][['player','target_gw','expected_minutes_original','expected_minutes_candidate','xpts_fixture_original','xpts_fixture_candidate']].to_dict('records')))
  print('PAIRED_LIVE_SAMPLER_COMPLETE',len(paired),flush=True)
if __name__=='__main__':main()
