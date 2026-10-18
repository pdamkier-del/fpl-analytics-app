import pandas as pd
import pytest
from audit_historical_pm_components import audit

def sample():
    predicted=pd.DataFrame([dict(fixture_uuid='f',player_uuid='p',mode='B',
        xp=3.,total_points=2.,**{x:0. for x in (
        'appearance_points','goal_points','assist_points','cs_points',
        'save_points','dc_points','negative_points','gc_points',
        'penalty_save_points','expected_bonus')})])
    actual=pd.DataFrame([dict(fixture_uuid='f',player_uuid='p',total_points=5.)])
    return predicted,actual

def test_component_unknown_not_false_zero():
    p,a=sample()
    rows=audit(p,a,'2025-26','B')
    assert rows[-1]['component']=='total_xP'
    assert rows[-1]['mae']==2.
    assert all(row['status']=='NOT_AVAILABLE' for row in rows[:-1])

def test_observed_assists_can_be_audited_separately():
    p,a=sample();p.loc[0,'assist_points']=1.;a['assist_points_actual']=3.
    rows=audit(p,a,'2025-26','B')
    assist=next(x for x in rows if x['component']=='assist_points')
    assert assist['status']=='VALID' and assist['mae']==2.

def test_missing_fixture_rejected():
    p,a=sample();a['fixture_uuid']='different'
    with pytest.raises(ValueError,match='Missing observed'):
        audit(p,a,'2025-26','B')

def test_actual_bonus_and_nonbonus_when_frozen_truth_has_bonus():
    p,a=sample()
    p.loc[0,'expected_bonus']=0.5
    a['bonus']=2.
    rows=audit(p,a,'2025-26','B')
    bonus=next(x for x in rows if x['component']=='expected_bonus')
    nonbonus=next(x for x in rows if x['component']=='nonbonus_points')
    assert bonus['status']=='VALID' and bonus['mae']==1.5
    assert nonbonus['status']=='VALID' and nonbonus['mae']==0.5
