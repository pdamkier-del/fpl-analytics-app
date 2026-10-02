"""No-argument tests, runnable without pytest via run_model_checks.py."""
from fpl_v1_1_model.role_classifier import template, classify_lineup, ROLES
from fpl_v1_1_model.role_history import RoleHistory, summarize_state
from pathlib import Path
import json
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def lineup(formation='4-2-3-1'):
    flat=['GK']+[r for layer in template(formation) for r in layer]
    return [{'slot':i+1,'player_uuid':str(i),'position':'G' if i==0 else 'M',
             'x':40.,'y':float(i*8)} for i in range(11)],{str(i):r for i,r in enumerate(flat)}


def test_cam_structural_templates():
    for formation in ['4-2-3-1','4-4-1-1','3-4-1-2']:
        roles=[r for layer in template(formation) for r in layer]
        assert len(roles)==10 and roles.count('CAM')==1
    assert template('3-4-2-1')[1][0]=='RWB'
    assert set(['GK','RB','RWB','RCB','CB','LCB','LB','LWB','RDM','DM','LDM','RCM','CM','LCM','CAM','RW','LW','ST'])<=set(ROLES)


def test_gameflow_average_x_does_not_override_cam():
    rows,geometry=lineup();cam=next(p for p,r in geometry.items() if r=='CAM')
    geometry[cam]='ST';rows[int(cam)]['x']=99
    result=classify_lineup('4-2-3-1',rows,geometry)
    assert result[cam]['final_role']=='CAM'
    assert result[cam]['disagreement'] and result[cam]['average_position_uncertain']


def test_paired_prior_supported_side_override():
    rows,geometry=lineup();geometry['5']='LDM';geometry['6']='RDM'
    rows[5].update(y=80);rows[6].update(y=20)
    priors={'5':{'q':{'LDM':.9,'RDM':.1},'evidence':5},'6':{'q':{'RDM':.9,'LDM':.1},'evidence':5}}
    result=classify_lineup('4-2-3-1',rows,geometry,priors)
    assert result['5']['final_role']=='LDM' and result['6']['final_role']=='RDM'
    result=classify_lineup('4-2-3-1',rows,geometry)
    assert result['5']['final_role']=='RDM'
    rows[5]['x']=None
    result=classify_lineup('4-2-3-1',rows,geometry,priors)
    assert result['5']['final_role']=='RDM' and result['5']['average_position_missing']


def test_q_h_cutoff_strict_and_future_invariant():
    history=RoleHistory()
    history.add_game(1,10,'a',[{'player_uuid':'p','role':'CAM','started':True,'minutes':90}])
    empty,_,_=history.state(1,10)
    assert empty=={}
    first,cap,_=history.state(1,11)
    assert abs(sum(first['p']['q'].values())-1)<1e-12
    assert first['p']['q']['CAM']>first['p']['q']['CM']
    assert first['p']['H']['CAM']>0 and all(0<=h<=1 for h in first['p']['H'].values())
    before=summarize_state(first['p'],cap)
    history.add_game(1,20,'b',[{'player_uuid':'p','role':'ST','started':True,'minutes':90}])
    state,capacities,_=history.state(1,11)
    assert state==first and summarize_state(state['p'],capacities)==before


def test_keeper_q_and_unknown_sub():
    history=RoleHistory()
    history.add_game(1,10,'a',[{'player_uuid':'g','role':'GK','started':True,'minutes':90},
                             {'player_uuid':'s','role':None,'started':False,'minutes':12}])
    state,_,_=history.state(1,11)
    assert state['g']['q']=={'GK':1.0}
    assert state['s']['q']=={}


def test_invalid_formation_is_explicit_low_confidence():
    rows,geometry=lineup()
    result=classify_lineup('invalid',rows,geometry,{'1':{'q':{'RWB':.9,'RB':.1},'evidence':4}})
    assert result['1']['final_role']=='RWB' and result['1']['role_confidence']=='low'
    assert result['1']['slot_role'] is None


def test_saved_predictions_are_aligned_cutoff_safe_and_exact_eleven():
    path=ROOT/'analysis/results/reproducible-role-v1/role_augmented_holdout_predictions.csv.gz'
    columns=['gw','fixture_uuid','player_uuid','team_id','cutoff','max_history_known_at',
             'baseline_p_start','role_aware_p_start','baseline_xmins','role_aware_xmins',
             'start_minutes_mean','cameo_minutes_mean','p_cameo_given_bench','evaluation_partition']
    frame=pd.read_csv(path,usecols=columns)
    assert len(frame)==13987 and set(frame.gw)==set(range(22,39))
    assert not frame.duplicated(['fixture_uuid','player_uuid']).any()
    assert set(frame.evaluation_partition)=={'frozen_oos'}
    known=pd.to_datetime(frame.max_history_known_at,utc=True)
    assert (known<pd.to_datetime(frame.cutoff,utc=True)).all()
    assert np.allclose(frame.groupby(['fixture_uuid','team_id']).role_aware_p_start.sum(),11,atol=1e-9)
    expected=frame.role_aware_p_start*frame.start_minutes_mean+(1-frame.role_aware_p_start)*frame.p_cameo_given_bench*frame.cameo_minutes_mean
    assert np.allclose(expected,frame.role_aware_xmins,atol=1e-9)
    baseline=pd.read_csv(ROOT/'analysis/results/v2-reproduced/pstart_v2_fixture_holdout_2025_26.csv')
    baseline=baseline[baseline.gw>=22]
    assert list(zip(frame.fixture_uuid,frame.player_uuid))==list(zip(baseline.fixture_uuid,baseline.player_uuid))
    assert np.allclose(frame.baseline_p_start,baseline.p_start_v2,atol=1e-12)
    assert np.allclose(frame.baseline_xmins,baseline.expected_minutes_v2,atol=1e-12)
    models=json.loads((path.parent/'models.json').read_text())
    assert all(not any('posthoc' in c or c in ['y','minutes','outcome_known_at'] for c in m['features']) for m in models.values())


def test_saved_disagreement_population_and_missing_coordinate_flags():
    frame=pd.read_csv(ROOT/'analysis/results/reproducible-role-v1/role_disagreements.csv')
    assert len(frame)==1052
    assert int(frame.average_position_missing.sum())==4
    assert (frame.loc[frame.average_position_missing,'final_role']==frame.loc[frame.average_position_missing,'slot_role']).all()
    assert (frame.slot_role!=frame.position_role).all()
    assert frame.prior_q.map(json.loads).map(lambda q: not q or abs(sum(q.values())-1)<1e-10).all()
