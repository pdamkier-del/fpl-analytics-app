from dataclasses import replace
import numpy as np
import pytest
from fpl_v1_1_model.experimental_receiver_conversion import receiver_rates, shadow_receiver_conversion
from fpl_v1_1_model.experimental_pm_conversion import event_weights
from fpl_v1_1_model.joint_simulator import MatchSimInput, PlayerSimInput, simulate_many


def example():
    return MatchSimInput('h', 'a', 2., 1., tuple(
        PlayerSimInput(str(i), 'h' if i < 2 else 'a', 'MID', 1., 0., 90., 10.,
                       goal_weight=1., assist_weight=1.) for i in range(4)),
        lambda_home_penalties=.2, home_penalty_conversion=.8)


def test_active_chance_weighting_ignores_absent_finisher():
    inp = example()
    spec = dict(base_weights={p.player_id: 1. for p in inp.players},
                factors={'0': 2., '1': .5, '2': 1., '3': 1.})
    exposure = {p.player_id: float(p.player_id != '0') for p in inp.players}
    rates, _ = receiver_rates(inp, spec, exposure)
    assert rates['h']['ordinary'] == pytest.approx((2 - .16) * .5)
    exposure['0'] = 1.
    rates, _ = receiver_rates(inp, spec, exposure)
    assert rates['h']['ordinary'] == pytest.approx((2 - .16) * 1.25)


def test_combined_scales_once_and_keeps_penalties():
    inp = example()
    factors = {p.player_id: 2. for p in inp.players}
    adjusted = event_weights(inp, factors)
    spec = dict(base_weights={p.player_id: p.goal_weight for p in inp.players}, factors=factors)
    rates, _ = receiver_rates(adjusted, spec, {p.player_id: 1. for p in inp.players})
    assert rates['h']['total'] == pytest.approx((2 - .16) * 2 + .16)
    assert adjusted.lambda_home_penalties == inp.lambda_home_penalties
    assert adjusted.home_penalty_conversion == inp.home_penalty_conversion


def test_no_active_mass_is_neutral_and_bad_evidence_rejected():
    inp = example()
    spec = dict(base_weights={p.player_id: 1. for p in inp.players},
                factors={p.player_id: 1. for p in inp.players})
    rates, _ = receiver_rates(inp, spec, {p.player_id: 0. for p in inp.players})
    assert rates['h']['total'] == pytest.approx(2.)
    spec['factors']['0'] = float('nan')
    with pytest.raises(ValueError):
        receiver_rates(inp, spec, {p.player_id: 1. for p in inp.players})


def test_neutral_adapter_is_draw_identical_and_restores_after_failure():
    from fpl_v1_1_model import joint_simulator as sim, experimental_player_pm as pm
    inp = example()
    factors = {p.player_id: 1. for p in inp.players}
    original = simulate_many(inp, n=100, seed=71)
    with shadow_receiver_conversion(inp, factors):
        assert simulate_many(inp, n=100, seed=71) == original
    saved = (sim.simulate_match, sim._sample_minutes, pm.lineup_rates)
    with pytest.raises(RuntimeError):
        with shadow_receiver_conversion(inp, factors):
            raise RuntimeError('stop')
    assert (sim.simulate_match, sim._sample_minutes, pm.lineup_rates) == saved


def test_half_match_change_has_half_exposure_effect():
    inp = example()
    spec = dict(base_weights={p.player_id: 1. for p in inp.players},
                factors={'0': 2., '1': 1., '2': 1., '3': 1.})
    e = {p.player_id: np.ones(90) for p in inp.players}
    e['0'][:45] = 0.
    rates, _ = receiver_rates(inp, spec, e)
    assert rates['h']['ordinary'] == pytest.approx((2 - .16) * 1.25)
