#!/usr/bin/env python3
"""Opt-in duration candidate through original PM builders; no public publication.
Rebuilds all exposure-dependent components, never only edits displayed minutes.
"""
import sys,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.minutes import project_minutes
from fpl_v1_1_model.role_event_priors import QCOLS
from build_locked_live_v2_baseline import exact_frozen_duration_constants
from run_rolling_vfinal_gw6_38 import load_models
from vfinal_replay_components import build_fixture_components
from run_v4_performance_rating_experiment import RECENT_FEATURES
from assemble_live_vfinal_inputs import assemble
from run_live_vfinal_joint_simulation import simulate,POINT_COMPONENTS
B=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1';W=ROOT/'work/live-final-model';OUT=ROOT/'analysis/results/full-model-audit-20261012'

def rebuild(joined):
 history=pd.read_csv(B/'player_fixture_observations.csv.gz');history['available_at']=pd.to_datetime(history.available_at,utc=True);history['kickoff_at']=pd.to_datetime(history.kickoff_at,utc=True)
 cut=pd.Timestamp(joined.cutoff.iloc[0]);history=history[history.available_at<cut].copy()
 training=pd.read_csv(B/'reconstructed_training_features.csv.gz',low_memory=False);classified=pd.read_csv(B/'classified_starters.csv.gz');classified['available_at']=pd.to_datetime(classified.available_at,utc=True)
 if 'max_history_known_at' not in training:
  by={int(t):g.available_at.drop_duplicates().sort_values() for t,g in classified.groupby('team_id')}
  training['max_history_known_at']=[next(iter(reversed(by.get(int(r.team_id),pd.Series([],dtype='datetime64[ns, UTC]'))[by.get(int(r.team_id),pd.Series([],dtype='datetime64[ns, UTC]'))<pd.Timestamp(r.cutoff)].tolist())),None) for r in training.itertuples()]
 rolehist=training[['fixture_uuid','player_uuid','team_id','cutoff','max_history_known_at']+QCOLS].copy();perf=pd.read_csv(W/'current_performance_ledger.csv.gz');perf['available_at']=pd.to_datetime(perf.available_at,utc=True);models=load_models()
 preliminary_cols=pd.read_csv(B/'vfinal_player_event_components_6gw.csv.gz',nrows=0).columns
 remove=[c for c in preliminary_cols if c not in ['fixture_uuid','player_uuid','fpl_element','target_gw','team_id','expected_minutes','p_start','live_eligibility_applied','cutoff']];out=[]
 for index,(fx,g) in enumerate(joined.groupby('fixture_uuid',sort=True)):
  if index%10==0:print('Original PM components rebuilt for fixtures',index,flush=True)
  rg=g.drop(columns=remove+RECENT_FEATURES,errors='ignore').copy();rg['expected_minutes']=rg.xmins;rg['evidence_at']=cut;h=int(g.home_team_id.iloc[0]);a=int(g.away_team_id.iloc[0])
  out.append(build_fixture_components(rg,history,rolehist,cut,models['attack'],models['dc'],models['neg'],models['ga'],models['dc_model'],models['dc_cal'],perf,h,a,float(g.lambda_home_goals.iloc[0]),float(g.lambda_away_goals.iloc[0]),float(g.assist_probability_per_goal.iloc[0]),season='2026-27'))
 # Penalty/BPS covariates are role/rate90/history, not expected duration. Reuse
 # the same cutoff-matched immutable components; no new fitting or priors.
 return assemble(pd.concat(out,ignore_index=True),pd.read_csv(B/'vfinal_live_penalty_inputs.csv.gz'),pd.read_csv(B/'vfinal_live_bps_components.csv.gz'))

def main():
 selection=json.loads((OUT/'duration_walkforward_report.json').read_text());half=float(selection['selected_half_life']);original_half=exact_frozen_duration_constants()['DUR_H']
 j=pd.read_csv(B/'vfinal_live_joined_inputs.csv.gz',low_memory=False);history=pd.read_csv(B/'player_fixture_observations.csv.gz');cut=pd.Timestamp(j.cutoff.iloc[0]);assert (pd.to_datetime(history.available_at,utc=True)<cut).all()
 hist={uid:g.sort_values('kickoff_at').to_dict('records') for uid,g in history.groupby('player_uuid')};means={};old={}
 for uid in j.player_uuid.unique():
  past=hist.get(uid,[]);old[uid]=project_minutes(past,duration_half_life=original_half).expected_minutes_given_start;means[uid]=project_minutes(past,duration_half_life=half).expected_minutes_given_start
 if not np.allclose(j.start_minutes_mean,j.player_uuid.map(old),rtol=0,atol=1e-10):raise ValueError('Original duration source does not reproduce')
 candidate=j.copy();candidate['start_minutes_mean']=candidate.player_uuid.map(means);candidate['xmins']=candidate.p_start*candidate.start_minutes_mean+(1-candidate.p_start)*candidate.mm_q_sub*candidate.mm_sub_minutes
 original=rebuild(j);new=rebuild(candidate);saved=pd.read_csv(B/'vfinal_live_full_simulator_input.csv.gz',low_memory=False)
 key=['fixture_uuid','player_uuid'];check=original.merge(saved,on=key,validate='one_to_one',suffixes=('_rebuilt','_saved'))
 watch=['control_p_start','control_xmins','goal_mu','assist_mu','mu_dc','p_yellow','p_red','p_own_goal','lambda_saves','bg_mean_rate90','bg_sd90','lambda_pen','pen_weight']
 diffs={c:float(np.max(abs(check[c+'_rebuilt']-check[c+'_saved']))) for c in watch}
 if any(v>1e-10 for v in diffs.values()):raise ValueError('Original PM component rebuilding failed: '+str(diffs))
 seeds={fx:i for i,fx in enumerate(sorted(original.fixture_uuid.unique()))};xp,_=simulate(original,draws=400,fixture_seed_offsets=seeds);savedxp=pd.read_csv(B/'live_vfinal_fixture_xp.csv.gz');compare=xp.merge(savedxp,on=key,suffixes=('_rerun','_saved'),validate='one_to_one')
 if any(not np.array_equal(compare[c+'_rerun'],compare[c+'_saved']) for c in ['xpts_fixture','expected_minutes',*POINT_COMPONENTS]):raise ValueError('Original PM output is not exactly reproduced')
 pred,_=simulate(new,draws=400,fixture_seed_offsets=seeds);paired=xp.merge(pred,on=key,suffixes=('_original','_candidate'),validate='one_to_one').merge(j[key+['player','fpl_element','target_gw']],on=key,validate='one_to_one')
 paired.to_csv(OUT/'duration_pm_paired.csv.gz',index=False,compression='gzip');new.to_csv(OUT/'duration_pm_shadow_inputs.csv.gz',index=False,compression='gzip')
 report=dict(classification='DURATION_CANDIDATE_ORIGINAL_PM_SHADOW_NOT_PROMOTED',cutoff=str(cut),selected_half_life=half,selection_period=selection['selection'],original_component_max_abs_delta=diffs,original_pm_outputs_exact=True,rows=len(paired),draws=400,full_mm_refit=False,full_ts_accuracy_test=False,promotion_allowed=False,locked_model_active=False,focus=paired[paired.player.isin(['Haaland','Saka'])][['player','target_gw','expected_minutes_original','expected_minutes_candidate','xpts_fixture_original','xpts_fixture_candidate']].sort_values(['player','target_gw']).to_dict('records'),limitations=['Original start/sub/workload/role probabilities held fixed; only shared conditional starter duration changes','Goal/assist allocation, DefCon calibration, discipline and own-goal probability are recomputed by the original PM builder','Current future point outcomes are not yet observed','Historical origin-safe full six-GW TS inputs remain incomplete'])
 (OUT/'duration_pm_shadow_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
