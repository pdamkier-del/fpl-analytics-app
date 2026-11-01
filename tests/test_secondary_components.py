"""Protect evidence boundaries in the isolated component audit."""
import numpy as np
import pandas as pd
from secondary_components import observed
from secondary_component_report import metric,allowed


def test_missing_component_labels_are_not_zero_or_inferred_from_total_points():
    y=observed(dict(minutes=90,total_points=12,goals=2), '2025-26')
    for name in ('cs','saves','save_pts','penalty_save_pts','dc_hit','dc_pts','bonus','bps','negative_pts'):
        assert np.isnan(y[name]), name


def test_cs_uses_player_concessions_and_sixty_minute_boundary():
    # A departing player keeps a CS even when his team concedes later.
    assert observed(dict(minutes=60,goals_conceded_on_pitch=0),'2025-26')['cs']==1
    assert observed(dict(minutes=59,goals_conceded_on_pitch=0),'2025-26')['cs']==0
    assert observed(dict(minutes=60,goals_conceded_on_pitch=1),'2025-26')['cs']==0


def test_dc_uses_official_award_label_instead_of_third_party_count():
    y=observed(dict(defcon_count=14,minutes=90),'2025-26')
    assert np.isnan(y['dc_hit'])
    assert np.isnan(y['dc_pts'])
    assert observed(dict(defcon_points=2),'2025-26')['dc_hit']==1


def test_binary_metrics_exclude_missing_labels_and_handle_zero_probabilities():
    df=pd.DataFrame(dict(fixture_uuid=['a','b','c'],player_uuid=['x','x','y'],p_cs=[0.,1.,.8],y_cs=[1.,0.,np.nan]))
    m=metric(df,'cs')
    assert m['n']==2
    assert m['brier']==1
    assert np.isfinite(m['log_loss'])


def test_fwd_has_no_fpl_cs_award_and_outfield_has_no_save_points():
    df=pd.DataFrame({'position':['GK','DEF','MID','FWD']})
    assert list(allowed(df,'cs').position)==['GK','DEF','MID']
    assert list(allowed(df,'save_pts').position)==['GK']
