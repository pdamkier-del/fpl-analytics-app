from dataclasses import dataclass, replace
from types import SimpleNamespace

import pandas as pd
import pytest

from compare import ARMS, fixed_proposer, variant, weights
from originals import expected_edge, market_decision


@dataclass(frozen=True)
class Config:
    weights: tuple = weights(.6)
    hit_uncertainty_buffer: float = 1.
    discount_transfer_costs: bool = False
    beam_width: int = 20


def test_weight_arms_change_only_objective_weights():
    config = Config()
    for arm in list(ARMS)[:5]:
        assert variant(config, arm) == replace(config, weights=weights(ARMS[arm]))
    assert variant(config, "discount_costs") == replace(config, discount_transfer_costs=True)
    assert variant(config, "zero_buffer") == replace(config, hit_uncertainty_buffer=0.)
    assert variant(config, "rho100").weights == (1.,) * 6


def test_proposer_uses_frozen_suffix_and_restores_hooks_after_exception():
    def prepare(meta, origin, gws, weights, top):
        return weights

    def generate(state, meta, origin, gws, weights, *rest):
        return weights, rest

    planner = SimpleNamespace(_prepare_local_candidates=prepare, _fast_local_candidate_squads=generate)
    with pytest.raises(ValueError, match="contiguous"):
        with fixed_proposer(planner, 12, weights(.6)):
            assert planner._prepare_local_candidates(None, None, [14, 15], [1, 1], 18) == (.36, .216)
            assert planner._fast_local_candidate_squads(None, None, None, [16, 17], [1, 1], 5) == (
                (.1296, .07776), (5,))
            planner._prepare_local_candidates(None, None, [13, 15], [1, 1], 18)
    assert planner._prepare_local_candidates is prepare
    assert planner._fast_local_candidate_squads is generate


def test_market_prefers_roll_only_within_tolerance_and_no_additional_hit():
    assert market_decision(.25, .1, 0, 0, 1) == "switch_to_roll"
    assert market_decision(.251, .1, 0, 0, 1) == "outside_near_tie"
    assert market_decision(-.01, .1, 0, 0, 1) == "outside_near_tie"
    assert market_decision(.10, .1, 0, 4, 1) == "extra_hits_excluded"
    assert market_decision(.10, None, 0, 0, 1) == "blocked_market_vintage"
    assert market_decision(.10, 0, 0, 0, 1) == "keep_point_action"
    assert market_decision(.0, None, 0, 0, 0) == "already_roll"


def test_market_edge_uses_sale_price_and_refuses_stale_or_missing_prices():
    action = SimpleNamespace(outgoing=(1,), incoming=(2,))
    quotes = pd.DataFrame({"p_fall": [.1, .5], "p_rise": [.5, .2], "price": [51, 55]}, index=[1, 2])

    def sale(paid, current):
        return current if current < paid else paid + (current - paid) // 2

    edge = expected_edge(quotes, {1: 51, 2: 55}, {1: 50}, action, sale)
    assert edge == 1.
    assert expected_edge(quotes, {1: 50, 2: 55}, {1: 50}, action, sale) is None
    assert expected_edge(quotes.iloc[:1], {1: 51, 2: 55}, {1: 50}, action, sale) is None
