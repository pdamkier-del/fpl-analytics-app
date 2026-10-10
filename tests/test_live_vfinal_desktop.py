import importlib.util
from pathlib import Path
import pandas as pd
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('desktop',ROOT/'scripts/build_live_vfinal_desktop.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def fixture():
    inp=pd.DataFrame([dict(fixture_uuid='f',player_uuid='p',fpl_element=1,gw=6,target_gw=7,team_id=1,cutoff='2026-10-10T07:00:00Z',live_eligibility_applied=False,control_p_start=.8,p_cameo_given_bench=.2,control_xmins=70.,expected_minutes=70.,target_kickoff='2026-10-17T14:00:00Z')])
    pred=pd.DataFrame([dict(fixture_uuid='f',player_uuid='p',gw=7,xpts_fixture=2.,expected_minutes=68.,penalty_miss_points=0.,**{c:(2. if c=='appearance_points' else 0.) for c in m.POINT_COMPONENTS})])
    bootstrap={'elements':[dict(id=1,team=1,web_name='Test',element_type=3,now_cost=50)],'teams':[dict(id=1,name='Test club')]}
    audit={'verified_player_match_rows':1,'quarantined_rows':1,'missing_fields':{'was_fouled':1}}
    return inp,pred,bootstrap,audit

def test_target_gw_is_not_origin_feature_gw():
    result=m.build(*fixture());assert result['players'][0]['weeks'][0]['gw']==7
    assert result['locked_model_active'] is False

def test_missing_forecast_identity_fails_closed():
    i,p,b,a=fixture();p.loc[0,'player_uuid']='wrong'
    with pytest.raises(ValueError,match='identity coverage'):m.build(i,p,b,a)

def test_point_component_disagreement_rejected():
    i,p,b,a=fixture();p.loc[0,'xpts_fixture']=3
    with pytest.raises(ValueError,match='components mismatch'):m.build(i,p,b,a)

def test_unavailable_simulated_points_rejected():
    i,p,b,a=fixture();i['live_eligibility_applied']=True
    with pytest.raises(ValueError,match='Unavailable'):m.build(i,p,b,a)
