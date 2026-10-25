"""Integrity failures must not produce a misleading player explanation."""
import copy,json
import pandas as pd
import pytest
from trace_player_points import build_trace,load_inputs
from fpl_v1_1_model.forecast_snapshot import seal_forecast
from run_live_vfinal_joint_simulation import POINT_COMPONENTS


def fixture():
    c=dict.fromkeys(POINT_COMPONENTS,0.);c['appearance_points']=1.;c['cs_points']=1.
    match=dict(fixture_uuid='f',kickoff='2026-11-01T12:00:00Z',p_start=.5,p_60_plus=.5,p_90=.5,xmins=45.,pm_analytic_minutes=45.,simulated_minutes=45.,xpts=2.,components=c,penalty_miss_points_subset_of_negative=0.,distribution={'draws':2})
    week=dict(gw=1,xpts=2.,xmins=45.,pm_analytic_minutes=45.,fixtures=[match],scenarios={'minutes':[0,90],'points':[0,4]})
    f=seal_forecast(dict(model='B-MM-PM-TS-v1',scope='prospective_preview',locked_model_active=False,gws=[1],data_asof='2026-10-25T12:00:00Z',input_sha256={},minute_sampler_audit={'sampler':'B-MM-PM-TS-v1','all_MM_to_PM_means_consistent':True},scenario_contract={'version':'shared-PM-match-draws-v1','draws':2},players=[dict(id=100,player_uuid='p',name='Player',team='Club',team_id=1,position=3,weeks=[week])]))
    inputs=pd.DataFrame([dict(fixture_uuid='f',player_uuid='p',fpl_element=100,team_id=1,lambda_home_goals=1.5)]).set_index(['fixture_uuid','player_uuid'])
    return f,inputs


def test_trace_preserves_existing_values_and_seal_without_estimation():
    f,inputs=fixture();before=copy.deepcopy(f);t=build_trace(f,inputs)
    assert f==before
    assert t['rows'][0]['PM']['xpts']==2.
    assert t['rows'][0]['TS']['source_forecast_sha256']==f['forecast_sha256']
    assert t['rows'][0]['upstream_PM_inputs']['match_environment']=={'lambda_home_goals':1.5}
    assert t['probabilities_reestimated']is False
    assert t['selected_NP_head_verified']is False
    assert t['full_model_certification']is False


def test_tampered_forecast_fails_closed():
    f,inputs=fixture();f['players'][0]['name']='Changed'
    with pytest.raises(ValueError,match='checksum'):build_trace(f,inputs)


def test_wrong_source_club_fails_closed():
    f,inputs=fixture();inputs['team_id']=2
    with pytest.raises(ValueError,match='identity'):build_trace(f,inputs)


def test_resealed_missing_component_fails_closed():
    f,inputs=fixture();del f['players'][0]['weeks'][0]['fixtures'][0]['components']['goal_points']
    with pytest.raises(ValueError,match='components'):build_trace(seal_forecast(f),inputs)


def test_mismatched_input_file_fails_closed(tmp_path):
    (tmp_path/'pm.csv.gz').write_bytes(b'wrong data')
    with pytest.raises(ValueError,match='checksum'):load_inputs({'input_sha256':{'pm.csv.gz':'0'*64}},tmp_path)


def test_wrong_selected_np_file_fails_closed(tmp_path):
    f,inputs=fixture();path=tmp_path/'wrong.csv.gz';path.write_bytes(b'wrong NP')
    f['nonpenalty_goal_head']={'goal_head_audit_sha256':'0'*64}
    f['players'][0]['weeks'][0]['fixtures'][0]['penalty']=dict.fromkeys(['expected_nonpenalty_goals','expected_penalty_goals','expected_missed_penalties','p_takes_penalty','p_scores_penalty','team_p_at_least_one','team_simulated_p_at_least_one'],0.)
    with pytest.raises(ValueError,match='nonpenalty'):build_trace(seal_forecast(f),inputs,path)
