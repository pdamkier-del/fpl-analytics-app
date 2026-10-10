"""Regression evidence for unchanged frozen MM and target data isolation."""
import numpy as np
import pandas as pd
import pytest
from fpl_v1_1_model.mm_release import validate_mm_release
from run_mm_v2_team_news_availability_experiment import policy_caps
from run_mm_unified_official_roles import compose
from fpl_v1_1_model.rating_history import build_rating_features

def test_frozen_hard_out_substitute_branch_contract_conflict():
    # This proves current behavior; it deliberately does not patch frozen math.
    f=pd.DataFrame({'team_news_state':['OUT','SUSPENDED'],
                    'team_news_scoped_chance':[0.,0.],'start_minutes_mean':[80.,80.]})
    assert np.array_equal(policy_caps(f,'soft_0.5_0.1'),[0.,0.])
    assert np.array_equal(compose(f,np.array([0.,0.]),np.array([.2,.2]),np.array([20.,20.])),[4.,4.])

def test_target_and_post_cutoff_ratings_do_not_enter_live_features():
    target=pd.DataFrame({'player_uuid':['p'],'cutoff':['2026-10-10T12:00:00Z'],'expected_role':['CAM']})
    old=pd.DataFrame({'provider':['FotMob'],'player_uuid':['p'],'match_id':['past'],
                       'available_at':['2026-10-09T12:00:00Z'],'rating':[7.]})
    future=pd.DataFrame({'provider':['FotMob'],'player_uuid':['p'],'match_id':['future'],
                       'available_at':['2026-10-10T12:00:00Z'],'rating':[10.]})
    a=build_rating_features(target,old)
    b=build_rating_features(target,pd.concat([old,future],ignore_index=True))
    pd.testing.assert_frame_equal(a,b)

def test_frozen_formula_output_is_rejected_by_existing_release():
    rows=[]
    for i in range(12):
        rows.append(dict(season='2026-27',gw=6,fixture_uuid='f',team_id=1,player_uuid=str(i),
            player=str(i),team='A',pos='MID',cutoff='2026-10-10T08:00:00Z',
            p_start=0. if i==11 else 1.,xmins=4. if i==11 else 80.,
            expected_role='CAM',xi_assigned_role='CAM',xi_formation='4-2-3-1',
            team_news_state='OUT' if i==11 else 'AVAILABLE',team_news_availability_cap=0. if i==11 else 1.))
    with pytest.raises(ValueError,match='hard unavailable player has positive xmins'):
        validate_mm_release(pd.DataFrame(rows))
