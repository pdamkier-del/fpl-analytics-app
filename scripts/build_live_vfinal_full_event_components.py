#!/usr/bin/env python3
"""Use the original rolling-vFinal component builder, including role/DC/own goals.

The preliminary deadline rates are not sufficient for vFinal. No formula is
reimplemented here: this calls vfinal_replay_components.build_fixture_components.
"""
import json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_rolling_vfinal_gw6_38 import load_models
from vfinal_replay_components import build_fixture_components
from fpl_v1_1_model.role_event_priors import QCOLS
from run_v4_performance_rating_experiment import RECENT_FEATURES
from audit_current_locked_inputs import csvgz,dump
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1';WORK=ROOT/'work/live-final-model'


def build():
    joined=pd.read_csv(BASE/'vfinal_live_joined_inputs.csv.gz',low_memory=False)
    history=pd.read_csv(BASE/'player_fixture_observations.csv.gz')
    history['available_at']=pd.to_datetime(history.available_at,utc=True)
    history['kickoff_at']=pd.to_datetime(history.kickoff_at,utc=True)
    cut=pd.Timestamp(joined.cutoff.iloc[0]);history=history[history.available_at<cut].copy()
    training=pd.read_csv(BASE/'reconstructed_training_features.csv.gz',low_memory=False)
    classified=pd.read_csv(BASE/'classified_starters.csv.gz');classified['available_at']=pd.to_datetime(classified.available_at,utc=True)
    if 'max_history_known_at' not in training:
        by={int(t):g.available_at.drop_duplicates().sort_values() for t,g in classified.groupby('team_id')}
        training['max_history_known_at']=[next(iter(reversed(by.get(int(r.team_id),pd.Series([],dtype='datetime64[ns, UTC]'))[by.get(int(r.team_id),pd.Series([],dtype='datetime64[ns, UTC]'))<pd.Timestamp(r.cutoff)].tolist())),None) for r in training.itertuples()]
    rolehist=training[['fixture_uuid','player_uuid','team_id','cutoff','max_history_known_at']+QCOLS].copy()
    perf=pd.read_csv(WORK/'current_performance_ledger.csv.gz');perf['available_at']=pd.to_datetime(perf.available_at,utc=True)
    models=load_models();out=[]
    preliminary_cols=pd.read_csv(BASE/'vfinal_player_event_components_6gw.csv.gz',nrows=0).columns
    remove=[c for c in preliminary_cols if c not in ['fixture_uuid','player_uuid','fpl_element','target_gw','team_id','expected_minutes','p_start','live_eligibility_applied','cutoff']]
    for fx,g in joined.groupby('fixture_uuid',sort=True):
        rg=g.drop(columns=remove+RECENT_FEATURES,errors='ignore').copy()
        rg['expected_minutes']=rg.xmins;rg['evidence_at']=cut
        h=int(g.home_team_id.iloc[0]);a=int(g.away_team_id.iloc[0])
        rg=build_fixture_components(rg,history,rolehist,cut,models['attack'],models['dc'],models['neg'],
                                   models['ga'],models['dc_model'],models['dc_cal'],perf,h,a,
                                   float(g.lambda_home_goals.iloc[0]),float(g.lambda_away_goals.iloc[0]),
                                   float(g.assist_probability_per_goal.iloc[0]),season='2026-27')
        out.append(rg)
    frame=pd.concat(out,ignore_index=True)
    if len(frame)!=len(joined):raise ValueError('Full original component coverage mismatch')
    csvgz(BASE/'vfinal_live_full_event_inputs.csv.gz',frame)
    dump(WORK/'live_full_event_component_audit.json',dict(rows=len(frame),fixtures=frame.fixture_uuid.nunique(),
         original_builder='vfinal_replay_components.build_fixture_components',role_priors=True,soft_performance_allocation=True,
         dc_soft_role_and_threshold_calibration=True,own_goals=True,math_changed=False,live_certified=False))
    print('ORIGINAL VFINAL FULL EVENT COMPONENTS',len(frame),flush=True)
if __name__=='__main__':build()
