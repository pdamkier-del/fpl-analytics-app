from dataclasses import replace
import numpy as np
import pytest

from fpl_v1_1_model import joint_simulator as sim
from fpl_v1_1_model.experimental_joint_appearances import (
    AppearanceKernel, appearance_sampler, capped_probabilities, sample_subset)
from test_physical_timeline import fixture


def test_feasible_probabilities_unchanged_and_infeasible_explicitly_reduced():
    q = np.array([0, 1, .8, .3])
    assert np.array_equal(capped_probabilities(q, 3), q)
    assert capped_probabilities(q, 1) == pytest.approx(q/q.sum())
    assert capped_probabilities(q, 0) == pytest.approx(np.zeros(4))
    for bad in [[np.nan], [-.1], [1.1]]:
        with pytest.raises(ValueError): capped_probabilities(bad, 5)


def test_rounding_preserves_marginals_and_shared_cap():
    rng = np.random.default_rng(37)
    for q, cap in [([0, 1, .8, .3], 3), ([.8]*8, 4), ([], 5)]:
        draws = np.array([sample_subset(q, cap, rng) for _ in range(6000)])
        assert (draws.sum(axis=1) <= cap).all()
        assert draws.mean(axis=0) == pytest.approx(capped_probabilities(q, cap), abs=.025)


def test_actual_simulator_has_eleven_starters_gk_coverage_and_at_most_five_cameos():
    inp = fixture()
    # Deliberately impossible independent bench probabilities.
    inp = replace(inp, players=tuple(replace(p, p_cameo_given_bench=.8)
                  if not p.is_keeper and p.p_start else p for p in inp.players))
    kernel = AppearanceKernel(inp, {})
    assert all(d['infeasible_lineup_probability'] == pytest.approx(1) for d in kernel.diagnostics)
    moments = {uid: [] for uid in kernel.moments}
    original = sim.simulate_match
    with appearance_sampler(kernel):
        rng = np.random.default_rng(123)
        for _ in range(800):
            result = sim.simulate_match(inp, rng)
            for team in ['H', 'A']:
                ps = [p for p in inp.players if p.team == team]
                assert sum(result[p.player_id].started for p in ps) == 11
                assert sum(result[p.player_id].minutes for p in ps if p.is_keeper) == 90
                assert sum(result[p.player_id].minutes > 0 and not result[p.player_id].started for p in ps) <= 5
            assert result['Hunavailable'].minutes == result['Aunavailable'].minutes == 0
            for uid in moments: moments[uid].append(result[uid].minutes)
    assert sim.simulate_match is original
    for uid, values in moments.items():
        assert abs(np.mean(values)-kernel.moments[uid]['x']) < 6*np.std(values)/np.sqrt(len(values)) + 1e-8
    with pytest.raises(RuntimeError):
        with appearance_sampler(kernel): raise RuntimeError('stop')
    assert sim.simulate_match is original


def test_invalid_role_mixture_cannot_silently_change_starts():
    from types import SimpleNamespace
    inp = fixture()
    ids = tuple(p.player_id for p in inp.players if p.team == 'H' and not p.is_keeper)[:10]
    with pytest.raises(ValueError, match='marginals'):
        AppearanceKernel(inp, {'H': [SimpleNamespace(players=ids, weight=1.)]})


def test_kernel_cannot_be_reused_for_other_inputs_or_duplicate_players():
    inp=fixture();kernel=AppearanceKernel(inp,{})
    with pytest.raises(ValueError,match='different fixture'):
        kernel.conditioned_input(replace(inp,lambda_home_goals=2.),np.random.default_rng(1))
    with pytest.raises(ValueError,match='identity'):
        AppearanceKernel(replace(inp,players=inp.players+(inp.players[0],)),{})


def test_minute_error_terms_reconcile_without_treating_absolute_terms_as_shares():
    from screen_joint_appearances import minute_terms
    for started,minutes in [(0,0),(0,23),(1,90),(1,43)]:
        terms=minute_terms(.7,.4,78.,18.,started,minutes)
        assert sum(terms)==pytest.approx(.7*78.+.3*.4*18.-minutes)
