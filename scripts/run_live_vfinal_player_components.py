#!/usr/bin/env python3
"""Frozen live vFinal preliminary player event rates across GW6–11.

Uses original deadline_components.player_components_at_deadline unchanged,
with cutoff-safe observed FPL GW1–5 xG/xA/DefCon/cards. Current GW hard
unavailability is gated by the approved unchanged-composition boundary.
NOT simulated vFinal xP, transfer or chip certification.
"""
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_rolling_vfinal_gw6_38 import load_models
from fpl_v1_1_model.live_availability_boundary import prepare_live_mm_release_candidate
from fpl_v1_1_model.deadline_components import player_components_at_deadline

WORK=ROOT/'work/live-final-model'
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
OUT=BASE/'vfinal_player_event_components_6gw.csv.gz'
AUDIT=WORK/'live_vfinal_player_component_audit.json'

def run(horizon_end=None):
    frozen=load_models()
    meta=json.loads((WORK/'source_manifest.json').read_text())
    gw=int(meta['target_gw']);source_capture=pd.Timestamp(meta['observed_at'])
    mm=pd.read_csv(WORK/'mm_frozen_diagnostic_six_gw.csv.gz',low_memory=False)
    ph=pd.read_csv(BASE/'player_fixture_observations.csv.gz',low_memory=False)
    cut=pd.to_datetime(mm.cutoff,utc=True,errors='raise').min()
    if cut<source_capture:raise ValueError('Inferred cutoff predates official source snapshot')
    if pd.to_datetime(mm.cutoff,utc=True).nunique()!=1:raise ValueError('Not one model cutoff')
    origin=mm[mm.target_gw.eq(gw)].copy()
    gated=prepare_live_mm_release_candidate(origin,
       p_start=origin.p_start.to_numpy(float),
       q_sub=origin.mm_q_sub.to_numpy(float),
       sub_minutes=origin.mm_sub_minutes.to_numpy(float),
       origin_gw=gw,news_scoped_gw=gw)
    horizon=mm[mm.target_gw.ne(gw)].copy()
    if horizon.team_news_state.ne('UNKNOWN').any():
        raise ValueError('Future eligibility contaminated by current news')
    horizon['live_eligibility_applied']=False
    mm=pd.concat([gated,horizon],ignore_index=True)
    if horizon_end is None:
        if len(mm)!=4002 or mm.fixture_uuid.nunique()!=60:
            raise ValueError('Incomplete six-GW frozen minute predictions')
    else:
        target=pd.read_csv(BASE/'source_feature_matrix.csv.gz')
        keys=['fixture_uuid','player_uuid']
        if set(mm.target_gw.astype(int))!=set(range(gw,int(horizon_end)+1)) or mm.duplicated(keys).any() or set(map(tuple,mm[keys].to_numpy()))!=set(map(tuple,target[keys].to_numpy())):
            raise ValueError('Incomplete current-half frozen minute predictions')
    ph['available_at']=pd.to_datetime(ph.available_at,utc=True,errors='raise')
    ph['kickoff_at']=pd.to_datetime(ph.kickoff_at,utc=True,errors='raise')
    if (ph.available_at>=cut).any():
        raise ValueError('Post-cutoff player event history')
    mm['expected_minutes']=mm.xmins.astype(float)
    mm['evidence_at']=pd.to_datetime(mm.cutoff,utc=True,errors='raise')
    if (mm.evidence_at>cut).any():
        raise ValueError('Fixture row timestamp beyond common as-of time')
    forecast=player_components_at_deadline(ph,mm,cut,
       attack=frozen['attack'],dc=frozen['dc'],discipline=frozen['neg'],
       season='2026-27')
    if len(forecast)!=len(mm):
        raise ValueError('Frozen player-component coverage incomplete')
    expected=['goal_rate90','assist_rate90','dc_rate90','dc_alpha',
       'yellow_rate90','red_rate90','p_yellow','p_red','mu_dc']
    if forecast[expected].isna().any().any():
        raise ValueError('Missing frozen vFinal event component')
    if (~np.isfinite(forecast[expected].to_numpy(float))).any():
        raise ValueError('Nonfinite frozen vFinal event component')
    keys=['fixture_uuid','player_uuid']
    extras=mm[keys+['fpl_element','target_gw','team_id','expected_minutes',
        'p_start','live_eligibility_applied']]
    result=extras.merge(forecast,on=keys,validate='one_to_one')
    if result.duplicated(keys).any():raise ValueError('Duplicated player event output')
    if ((result.live_eligibility_applied)&(result.expected_minutes>1e-8)).any():
        raise ValueError('Hard-out current GW still has minutes')
    result.to_csv(OUT,index=False,compression='gzip')
    audit={'classification':'FROZEN_VFINAL_PLAYER_EVENT_COMPONENTS_NOT_COMPLETE_PM',
         'origin_gw':gw,'player_fixture_rows':len(result),
         'gws':sorted(map(int,result.target_gw.unique())),
         'unique_players':int(result.fpl_element.nunique()),
         'historical_completed_player_fixture_rows':len(ph),
         'frozen_component':'fpl_v1_1_model.deadline_components.player_components_at_deadline',
         'frozen_params_unchanged':True,'estimated_event_columns':expected,
         'current_hard_unavailable_count':int(gated.live_eligibility_applied.sum()),
         'target_outcomes_used':0,'PM_xP_computed':False,'live_certified':False}
    AUDIT.write_text(json.dumps(audit,indent=2)+'\n')
    print('FROZEN VFINAL CURRENT PLAYER COMPONENTS',json.dumps(audit))
    return result
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--horizon-end',type=int)
    run(parser.parse_args().horizon_end)

