from dataclasses import dataclass
from itertools import combinations
from types import SimpleNamespace

import numpy as np
import pytest

from frontier import Player, global_squad, local_options, local_squad, sale_price, solution
from replay import add_terminal_value, estimate, interval, terminal_bonus


def pool():
    positions = [1] * 2 + [2] * 5 + [3] * 5 + [4] * 3
    owned = [Player(i, pos, i // 3, 50, 4.0) for i, pos in enumerate(positions)]
    return owned + [Player(15, 2, 5, 51, 6.0), Player(16, 3, 6, 52, 8.0)]


@pytest.mark.parametrize("market,sale", [(45, 45), (50, 50), (51, 50), (52, 51), (53, 51), (54, 52)])
def test_official_prices(market, sale):
    assert sale_price(50, market) == sale


def test_global_matches_exhaustive_and_one_move_exposes_a_step():
    players = pool()
    prices, options = local_options(players, {i: 50 for i in range(15)})
    legal = [s for s in combinations(players, 15)
             if [sum(p.position == pos for p in s) for pos in range(1, 5)] == [2, 5, 5, 3]]
    for budget in range(749, 754):
        candidates = [solution(s, prices) for s in legal if sum(p.price for p in s) <= budget]
        actual = global_squad(players, budget, prices)
        if candidates:
            assert actual.points == pytest.approx(max(c.points for c in candidates))
        else:
            assert actual is None
    assert local_squad(options, 750).points == 48
    assert local_squad(options, 751).points == 52
    assert local_squad(options, 752, 2).points == 52
    assert local_squad(options, 752, 3).points == 56
    assert local_squad(options, 753).points < global_squad(players, 753, prices).points


def test_realisable_value_uses_distribution_and_purchase_price():
    samples = {(6, 2, 0): [-1, 1, 2]}
    bonus = terminal_bonus(samples, 30, {7: 50}, {}, {7: 2}, 6)
    assert bonus({7: SimpleNamespace(purchase_price=50)}) == pytest.approx(0)
    assert bonus({7: SimpleNamespace(purchase_price=51)}) == pytest.approx(1)


def test_terminal_value_applied_once_and_restored_on_error():
    @dataclass
    class Node:
        state: object
        objective: float
        path: list
        rank_score: float

    planner = SimpleNamespace(PlannerNode=Node)
    state = SimpleNamespace(squad={})
    with pytest.raises(RuntimeError), add_terminal_value(planner, 2, lambda squad: 3):
        assert planner.PlannerNode(state, 8, [0], 9).objective == 8
        last = planner.PlannerNode(state, 8, [0, 0], 9)
        assert (last.objective, last.rank_score) == (11, 12)
        raise RuntimeError
    assert planner.PlannerNode is Node


def test_lambda_matches_each_prior_season_and_wildcard_status():
    def row(season, budget, slope, wc=False):
        return dict(season=season, gw=20, wc=wc, liquid=budget, step=1, slope=slope)
    rows = [row("old", 990, 2), row("old", 1000, 4), row("recent", 980, 6),
            row("old", 1000, 45, True)]
    assert estimate(rows, 20, 1002, False, 1) == 5
    assert estimate(rows, 20, 1002, True, 1) == 45
    assert estimate(rows, 20, 1002, False, 5) is None
    np.testing.assert_allclose(interval([2, 2, 2]), [2, 2])


def test_incomplete_seasons_fail_before_loading_forecasts(tmp_path):
    import json
    from replay import load_data
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "holdout": ["2025-26", "2026-27"],
        "seasons": [{"season": season, "ft_topup_gws": [], "weeks": {}} for season in
                    ("2024-25", "2025-26", "2026-27")],
    }))
    with pytest.raises(ValueError, match="missing deadline or outcome"):
        load_data(manifest, None)
