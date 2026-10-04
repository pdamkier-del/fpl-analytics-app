import numpy as np
import pytest
from fpl_v1_1_model.keeper import (
    SOTRateParams, SaveRateParams, KeeperShotModel, KeeperEventModel,
    blend_sot_rate, forecast_source_sot_mean, forecast_fpl_save_mean,
    sample_keeper_shots, sample_keeper_events, save_points,
    goals_conceded_deduction, keeper_event_points, expected_save_points_poisson,
    expected_gc_deduction_poisson,
)


def test_keeper_model_rejects_more_goals_than_sot():
    with pytest.raises(ValueError):
        KeeperShotModel(1.0,1.1)


def test_keeper_shot_draw_is_physically_coherent():
    rng=np.random.default_rng(26092026)
    model=KeeperShotModel(5.0,1.5)
    for _ in range(100):
        x=sample_keeper_shots(rng,model)
        assert x.shots_on_target_faced==x.goals_conceded+x.saves


def test_phase3g_goal_save_draw_is_physically_coherent():
    rng=np.random.default_rng(26092026)
    model=KeeperEventModel(1.4,2.8)
    for _ in range(100):
        x=sample_keeper_events(rng,model)
        assert x.shots_on_target_faced==x.goals_conceded+x.saves


def test_exact_fpl_keeper_buckets():
    assert [save_points(x) for x in range(7)]==[0,0,0,1,1,1,2]
    assert [goals_conceded_deduction(x) for x in range(5)]==[0,0,-1,-1,-2]
    assert keeper_event_points(saves=6,goals_conceded=2,penalty_saves=1)==6


def test_expected_bucket_points_are_nonlinear():
    e=expected_save_points_poisson(2.0)
    assert 0 < e < 2.0/3.0
    g=expected_gc_deduction_poisson(1.5)
    assert g < 0


def test_sot_blend_and_fitted_layers():
    assert blend_sot_rate(6,4,5,opponent_weight=.5)==5
    assert blend_sot_rate(0,0,5)==5
    sp=SOTRateParams(opponent_weight=.5,intercept=0,attacker_home_log_effect=0)
    assert forecast_source_sot_mean(6,4,5,attacker_was_home=False,params=sp)==5
    kp=SaveRateParams(intercept=0,sot_exponent=1,attacker_home_log_effect=0)
    assert forecast_fpl_save_mean(5,attacker_was_home=False,params=kp)==5


def test_source_sot_is_not_forced_to_equal_fpl_saves_plus_goals():
    # Provider SOT is a predictor definition. The final FPL event model may have
    # a different total mean after calibration to FPL saves and team goals.
    kp=SaveRateParams(intercept=-0.6,sot_exponent=1.1,attacker_home_log_effect=0)
    saves=forecast_fpl_save_mean(5,attacker_was_home=False,params=kp)
    model=KeeperEventModel(1.4,saves)
    assert model.lambda_sot_faced == pytest.approx(1.4+saves)
    assert model.lambda_sot_faced != pytest.approx(5.0)
