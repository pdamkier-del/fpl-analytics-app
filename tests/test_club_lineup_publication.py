import importlib.util
from pathlib import Path
import pandas as pd
import pytest
spec=importlib.util.spec_from_file_location('weekly_publish',Path(__file__).resolve().parents[1]/'scripts/publish_weekly_assets.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def sample():
    roles=['GK','RB','RCB','LCB','LB','RDM','LDM','RAM','CAM','LAM','ST']
    return pd.DataFrame([dict(fixture_uuid='f',team_id=1,target_gw=7,target_kickoff='2026-10-17',fpl_element=i+1,xi_selected_map=int(i<11),xi_assigned_role=roles[i] if i<11 else 'UNKNOWN',xi_formation='4-2-3-1' if i<11 else 'UNKNOWN',live_eligibility_applied=False,cutoff='now') for i in range(12)])

def test_export_keeps_original_assignment():
    frame=sample();before=frame.copy(deep=True)
    output=module.club_lineups(frame,dict(data_asof='now',checksums={'source':'hash'}))
    pd.testing.assert_frame_equal(frame,before)
    assert output['locked_model_active'] is False
    assert output['fixtures'][0]['layers']==[['GK'],['RB','RCB','LCB','LB'],['RDM','LDM'],['RAM','CAM','LAM'],['ST']]
    assert sum(p['selected'] for p in output['fixtures'][0]['players'])==11

@pytest.mark.parametrize('fault',['cutoff','slots','missing','unavailable'])
def test_reject_invalid_assignment(fault):
    frame=sample()
    if fault=='cutoff': frame.loc[0,'cutoff']='old'
    if fault=='slots': frame.loc[0,'xi_assigned_role']='ST'
    if fault=='missing': frame.loc[0,'xi_selected_map']=0
    if fault=='unavailable': frame.loc[0,'live_eligibility_applied']=True
    with pytest.raises(ValueError):module.club_lineups(frame,dict(data_asof='now',checksums={}))

def test_role_shares_are_copied_without_changing_assignment_or_inputs():
    frame=sample();frame['q_ST_slow']=0.;frame.loc[11,'q_ST_slow']=.75
    frame['q_RW_slow']=0.;frame.loc[11,'q_RW_slow']=.25
    before=frame.copy(deep=True)
    output=module.club_lineups(frame,dict(data_asof='now',checksums={}))
    pd.testing.assert_frame_equal(frame,before)
    p=output['fixtures'][0]['players'][11]
    assert not p['selected'] and p['role']=='UNKNOWN'
    assert p['observed_roles']==[{'role':'RW','share':.25},{'role':'ST','share':.75}]
    assert p['role_evidence'] is None
