from datetime import datetime,timezone,timedelta
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parents[1]/'src')]
from experimental_mm_role_profiles import infer_player_roles
from experimental_individual_role_mm import role_start_probability
from individual_mm_validation import fit_role, clustered_ci
CUT=datetime(2025,10,1,tzinfo=timezone.utc)
def event(days,start=True,mins=90,available=True):
 return dict(known_at=CUT-timedelta(days=days),started=start,minutes=mins,available=available)
def test_strict_boundary_unknown_and_absent_do_not_erase_role():
 past=[event(i) for i in range(1,20)]
 a=infer_player_roles(past,CUT)
 assert infer_player_roles(past+[event(0,False,0),event(1,False,0,None),event(2,False,0,False)],CUT)==a
 assert role_start_probability(past,cutoff=CUT)==role_start_probability(past+[event(0,False,0)],cutoff=CUT)
def test_duplicate_facts_rejected_and_sparse_profiles_shrink():
 with pytest.raises(ValueError):infer_player_roles([event(1),event(1)],CUT)
 a=infer_player_roles([event(1)],CUT,start_prior=.5)
 assert .5<a['p_start_given_available']<.6
 assert a['starter_minutes_mean']<80
 assert a['cameo_minutes_mean']==18
 assert infer_player_roles([event(1,False,30)],CUT)['cameo_minutes_mean']>18

def test_sustained_benching_gradually_changes_continuous_role():
 old=[event(i) for i in range(30,50)]
 a=infer_player_roles(old,CUT)
 b=infer_player_roles(old+[event(i,False,0) for i in range(1,10)],CUT)
 assert b['p_start_given_available']<a['p_start_given_available']
 assert b['p_start_given_available']>0

def test_expected_xi_and_hard_caps_are_jointly_respected():
 f=pd.DataFrame(dict(fixture_uuid=['f']*25,team_id=[1]*25,pos=['GK']*3+['DEF']*8+['MID']*9+['FWD']*5,new_p_start=[.4]*25,team_news_availability_cap=[0.]+[1.]*24))
 p=fit_role(f.iloc[:0],f,1.,'continuous')
 assert p.sum()==pytest.approx(11)
 assert p[:3].sum()==pytest.approx(1)
 assert p[0]==0

def test_bootstrap_identity_and_rmse_are_paired():
 f=pd.DataFrame(dict(season=['s']*4,fixture_uuid=['a','a','b','b'],player_uuid=['1','2','1','2'],team_id=[1]*4,p=[.5]*4,x=[40]*4,y=[1,0,1,0],minutes=[80,0,70,0]))
 r=clustered_ci(f,f,'fixture_uuid',20)
 assert all(v['delta']==0 and v['interval95']==[0.,0.] for v in r.values())

def test_cameo_scope_is_calibrated_without_reading_target_outcomes():
 from individual_mm_validation import calibrate_cameo
 n=400
 history=pd.DataFrame(dict(cutoff=['2025-01-01T00:00:00Z']*n,outcome_known_at=['2025-01-02T00:00:00Z']*n,y=[0]*n,minutes=[0,20]*(n//2),new_q_sub=[.9]*n,role_cameo=[.8]*n,role_exposure=[10.]*n,history_n=[10]*n,days_since_play=[7.]*n,pos=['MID']*n,team_news_state=['AVAILABLE']*n))
 target=history.iloc[:1].copy();target['cutoff']='2025-02-01 00:00:00+00:00';target['outcome_known_at']='2025-02-02T00:00:00Z'
 a=calibrate_cameo(target,history).role_q_calibrated.iloc[0]
 target['minutes']=90
 b=calibrate_cameo(target,history).role_q_calibrated.iloc[0]
 assert a==pytest.approx(b)
 assert .4<a<.6  # conditional-squad 0.8 is not copied into unconditional q
 target['team_news_state']='OUT'
 assert calibrate_cameo(target,history).role_q_calibrated.iloc[0]==0

@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1.])
def test_nonfinite_or_invalid_profile_settings_rejected(value):
 with pytest.raises(ValueError):infer_player_roles([],CUT,half_life_days=value)
 with pytest.raises(ValueError):role_start_probability([],cutoff=CUT,strength=value)
