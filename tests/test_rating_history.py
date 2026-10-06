import pandas as pd
import pytest

from fpl_v1_1_model.rating_history import validate_rating_ledger,build_rating_features


def ledger():
    return pd.DataFrame([
        {'provider':'fotmob','player_uuid':'p1','match_id':'m1','available_at':'2026-01-01T20:00:00Z','rating':6.0,'role':'CAM'},
        {'provider':'fotmob','player_uuid':'p1','match_id':'m2','available_at':'2026-01-08T20:00:00Z','rating':7.0,'role':'CAM'},
        {'provider':'sofascore','player_uuid':'p1','match_id':'m2','available_at':'2026-01-08T20:00:00Z','rating':8.0,'role':'CAM'},
        {'provider':'fotmob','player_uuid':'p2','match_id':'m3','available_at':'2026-01-07T20:00:00Z','rating':6.5,'role':'CAM'},
    ])


def test_rating_cutoff_excludes_future_match():
    targets=pd.DataFrame([{'player_uuid':'p1','cutoff':'2026-01-05T12:00:00Z','expected_role':'CAM'}])
    out=build_rating_features(targets,ledger(),min_role_reference=100)
    assert out.loc[0,'rating_hist_n']==1
    assert out.loc[0,'rating_recent']==pytest.approx(6.0)


def test_multiple_providers_collapse_same_match():
    targets=pd.DataFrame([{'player_uuid':'p1','cutoff':'2026-01-10T12:00:00Z','expected_role':'CAM'}])
    out=build_rating_features(targets,ledger(),min_role_reference=100)
    assert out.loc[0,'rating_hist_n']==2
    # m2 combines 7 and 8 => 7.5 before recency aggregation.
    assert out.loc[0,'rating_last']==pytest.approx(7.5)


def test_missing_history_is_neutral():
    targets=pd.DataFrame([{'player_uuid':'new','cutoff':'2026-01-10T12:00:00Z','expected_role':'CAM'}])
    out=build_rating_features(targets,ledger(),min_role_reference=100)
    assert out.loc[0,'performance_score']==pytest.approx(.5)


def test_duplicate_provider_match_rejected():
    x=ledger()
    x=pd.concat([x,x.iloc[[0]]],ignore_index=True)
    with pytest.raises(ValueError):
        validate_rating_ledger(x)
