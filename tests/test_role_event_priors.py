import numpy as np
import pandas as pd
import pytest
from fpl_v1_1_model.role_event_priors import QCOLS,role_priors_at_deadline

def fixtures():
    h=pd.DataFrame([dict(fixture_uuid='past',player_uuid=p,team_id=1,minutes=90,
        xg=x,xa=x,defcon_count=x*10,fpl_position='DEF',kickoff_at='2025-01-01T15:00Z',
        available_at='2025-01-01T18:00Z') for p,x in [('a',0),('b',1)]])
    def role(f,p,q):
        return dict(fixture_uuid=f,player_uuid=p,team_id=1,cutoff='2025-01-01T12:00Z',
                    max_history_known_at='2024-12-30T18:00Z',**dict.fromkeys(QCOLS,0.),**q)
    # dict update avoids duplicate keyword names for the chosen role.
    def make(f,p,col):
        d=role(f,p,{});d[col]=1;return d
    hr=pd.DataFrame([make('past','a','q_CB_slow'),make('past','b','q_RW_slow')])
    tr=pd.DataFrame([make('future','c','q_CB_slow')]);tr.cutoff='2025-01-03T12:00Z'
    roster=tr[['fixture_uuid','player_uuid','team_id']].assign(pos='DEF')
    return h,hr,roster,tr

def test_soft_mixture_and_exposure_shrinkage():
    h,hr,r,t=fixtures();t['q_CB_slow']=.75;t['q_RW_slow']=.25
    o=role_priors_at_deadline(h,hr,r,t,'2025-01-03T12:00Z',90).iloc[0]
    assert o.goal_position_prior90==.5
    assert np.isclose(o.goal_role_prior90,.75*.25+.25*.75)

def test_unknown_falls_back_exactly():
    h,hr,r,t=fixtures();t[QCOLS]=0
    o=role_priors_at_deadline(h,hr,r,t,'2025-01-03T12:00Z',90).iloc[0]
    assert not o.role_known and o.goal_role_prior90==o.goal_position_prior90

def test_future_outcomes_do_not_change_prior():
    h,hr,r,t=fixtures();o=role_priors_at_deadline(h,hr,r,t,'2025-01-03T12:00Z',90)
    extra=h.copy();extra.fixture_uuid='later';extra.available_at='2025-01-04T18:00Z';extra.xg=999
    n=role_priors_at_deadline(pd.concat([h,extra]),hr,r,t,'2025-01-03T12:00Z',90)
    pd.testing.assert_frame_equal(o,n)

def test_future_target_roles_rejected():
    h,hr,r,t=fixtures();t.cutoff='2025-01-04T12:00Z'
    with pytest.raises(ValueError,match='Future target'):role_priors_at_deadline(h,hr,r,t,'2025-01-03T12:00Z',90)

def test_invalid_probability_mass_rejected():
    h,hr,r,t=fixtures();t['q_RW_slow']=1
    with pytest.raises(ValueError,match='Role mass'):role_priors_at_deadline(h,hr,r,t,'2025-01-03T12:00Z',90)

def test_historical_roles_after_fixture_rejected():
    h,hr,r,t=fixtures();hr.cutoff='2025-01-02T12:00Z'
    with pytest.raises(ValueError,match='later than its fixture'):role_priors_at_deadline(h,hr,r,t,'2025-01-03T12:00Z',90)
