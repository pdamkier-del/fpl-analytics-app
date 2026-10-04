import pandas as pd

from fpl_xpts.season_replay import (
    OwnedPlayer, ReplayState, actual_team_points, best_normal_transfers, choose_chip, legalize_team_limit,
    selling_price, valid_squad,
)


def test_selling_price_uses_half_of_profit_rounded_down():
    assert selling_price(50, 55) == 52
    assert selling_price(50, 54) == 52
    assert selling_price(50, 47) == 47


def test_captain_falls_to_vice_and_autosub_respects_formation():
    rows = []
    ids = list(range(1, 16))
    positions = ["GKP", "GKP"] + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
    roles = ["C", "GK bench", "VC"] + ["XI"] * 9 + ["Bench 1", "Bench 2", "Bench 3"]
    for player_id, position, role in zip(ids, positions, roles):
        rows.append({"id": player_id, "position": position, "role": role})
    plan = pd.DataFrame(rows)
    actual = pd.DataFrame({"id": ids, "minutes": [0] + [90] * 14, "points": [0] + [2] * 14})
    score, autosubs = actual_team_points(plan, actual, None, 0)
    assert 2 in autosubs
    assert score == 24


def test_real_life_club_transfer_forces_squad_back_to_three_player_limit():
    positions = ["GKP"] * 2 + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
    teams = [1, 2, 3, 4, 5, 6, 7, 1, 1, 1, 8, 9, 10, 11, 12]
    meta = pd.DataFrame({
        "id": list(range(1, 17)),
        "web_name": [f"P{x}" for x in range(1, 17)],
        "position": positions + ["MID"],
        "team": teams + [13],
        "price_tenths": [50] * 16,
    })
    state = ReplayState({x: OwnedPlayer(x, 50) for x in range(1, 16)}, bank=0, free_transfers=1)
    origin = pd.DataFrame({"id": list(range(1, 17)), "gw": [5] * 16, "xpts_mean": [2.0] * 15 + [3.0]})
    moves = legalize_team_limit(state, meta, origin, 5)
    assert len(moves) == 1
    assert moves[0]["forced"] is True
    assert moves[0]["hit"] == 0
    assert valid_squad(meta, state.squad)


def test_simple_3gw_transfer_uses_rolling_three_gw_gain_and_exact_hit_cost():
    meta = pd.DataFrame({
        "id": [1, 2],
        "web_name": ["Owned", "Candidate"],
        "position": ["FWD", "FWD"],
        "team": [1, 2],
        "price_tenths": [50, 50],
    })

    # The candidate is worse now but better across the full rolling window.
    future_gain = pd.DataFrame({
        "id": [1, 1, 1, 2, 2, 2],
        "gw": [10, 11, 12, 10, 11, 12],
        "xpts_mean": [10.0, 0.0, 0.0, 0.0, 6.5, 6.0],
    })
    free_state = ReplayState({1: OwnedPlayer(1, 50)}, bank=0, free_transfers=1)
    free_move = best_normal_transfers(
        free_state, meta, future_gain, 10, max_total_transfers=1,
        transfer_policy="simple_3gw",
    )
    assert len(free_move) == 1
    assert free_move[0]["gain"] == 2.5
    assert free_move[0]["hit"] == 0
    assert free_move[0]["decision_cost"] == 2.16

    # With a two-point uncertainty buffer, a hit needs more than six xPts.
    for gain, expected_moves in ((5.9, 0), (6.1, 1)):
        hit_state = ReplayState({1: OwnedPlayer(1, 50)}, bank=0, free_transfers=0)
        hit_forecast = pd.DataFrame({
            "id": [1, 1, 1, 2, 2, 2],
            "gw": [10, 11, 12, 10, 11, 12],
            "xpts_mean": [0.0, 0.0, 0.0, gain / 3, gain / 3, gain / 3],
        })
        moves = best_normal_transfers(
            hit_state, meta, hit_forecast, 10, max_total_transfers=1,
            transfer_policy="simple_3gw",
        )
        assert len(moves) == expected_moves
        if moves:
            assert moves[0]["hit"] == 4
            assert moves[0]["decision_cost"] == 6.0
            assert moves[0]["net_gain"] > 0


def test_simple_3gw_can_bank_a_free_transfer_for_a_better_future_move():
    meta = pd.DataFrame({
        "id": [1, 2],
        "web_name": ["Owned", "Candidate"],
        "position": ["MID", "MID"],
        "team": [1, 2],
        "price_tenths": [50, 50],
    })
    for gain, free_transfers, expected_moves in (
        (2.0, 1, 0),   # Bank the FT: current gain is below its option value.
        (2.2, 1, 1),   # Use it: gain beats the 2.16 option value.
        (0.1, 5, 1),   # Use an expiring FT at the five-transfer cap.
    ):
        state = ReplayState({1: OwnedPlayer(1, 50)}, bank=0, free_transfers=free_transfers)
        forecast = pd.DataFrame({
            "id": [1, 1, 1, 2, 2, 2],
            "gw": [20, 21, 22, 20, 21, 22],
            "xpts_mean": [0.0, 0.0, 0.0, gain, 0.0, 0.0],
        })
        moves = best_normal_transfers(
            state, meta, forecast, 20, max_total_transfers=1,
            transfer_policy="simple_3gw",
        )
        assert len(moves) == expected_moves


def _valid_base_meta():
    positions = ["GKP"] * 2 + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
    return pd.DataFrame({
        "id": list(range(1, 16)),
        "web_name": [f"P{x}" for x in range(1, 16)],
        "position": positions,
        "team": list(range(1, 16)),
        "price_tenths": [50] * 15,
    })


def test_joint_transfers_find_downgrade_plus_upgrade_that_greedy_misses():
    meta = _valid_base_meta()
    meta.loc[meta.id == 8, "price_tenths"] = 100
    additions = pd.DataFrame({
        "id": [16, 17],
        "web_name": ["CheapMID", "PremiumFWD"],
        "position": ["MID", "FWD"],
        "team": [16, 17],
        "price_tenths": [50, 100],
    })
    meta = pd.concat([meta, additions], ignore_index=True)
    values = {pid: 0.0 for pid in meta.id}
    for pid in range(8, 13):
        values[pid] = 10.0
    values[16] = 9.0
    values[17] = 10.0
    origin = pd.DataFrame({"id": list(values), "gw": 10, "xpts_mean": list(values.values())})
    state = ReplayState(
        {pid: OwnedPlayer(pid, int(meta.set_index("id").loc[pid, "price_tenths"])) for pid in range(1, 16)},
        bank=0,
        free_transfers=2,
    )

    moves = best_normal_transfers(
        state, meta, origin, 10, max_total_transfers=5,
        transfer_policy="simple_3gw",
    )
    assert len(moves) == 2
    assert {move["in_id"] for move in moves} == {16, 17}
    assert {move["out_id"] for move in moves} == {8, 13}
    assert moves[0]["bundle_gain"] == 9.0
    assert abs(moves[0]["bundle_net_gain"] - 4.68) < 1e-9
    assert state.bank == 0
    assert valid_squad(meta, state.squad)


def test_joint_transfer_bundle_can_use_all_five_transfers():
    meta = _valid_base_meta()
    additions = pd.DataFrame({
        "id": list(range(16, 21)),
        "web_name": [f"NewDEF{x}" for x in range(1, 6)],
        "position": ["DEF"] * 5,
        "team": list(range(16, 21)),
        "price_tenths": [50] * 5,
    })
    meta = pd.concat([meta, additions], ignore_index=True)
    values = {pid: (10.0 if pid >= 16 else 0.0) for pid in meta.id}
    origin = pd.DataFrame({"id": list(values), "gw": 20, "xpts_mean": list(values.values())})
    state = ReplayState(
        {pid: OwnedPlayer(pid, 50) for pid in range(1, 16)},
        bank=0,
        free_transfers=5,
    )

    moves = best_normal_transfers(
        state, meta, origin, 20, max_total_transfers=5,
        transfer_policy="simple_3gw",
    )
    assert len(moves) == 5
    assert {move["in_id"] for move in moves} == set(range(16, 21))
    assert sum(int(move["hit"]) for move in moves) == 0
    assert abs(moves[0]["bundle_net_gain"] - (50.0 - 4 * 2.16)) < 1e-9
    assert valid_squad(meta, state.squad)


def _chip_table(rows):
    defaults = {
        "triple_captain": 0.0,
        "bench_boost": 0.0,
        "free_hit": 0.0,
        "wildcard": 0.0,
        "blank_teams": 0,
        "double_teams": 0,
        "schedule_confirmed": False,
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def test_chip_policy_waits_through_cold_start_and_for_better_visible_week():
    state = ReplayState({}, bank=0)
    cold_start = _chip_table([
        {"gw": 4, "triple_captain": 20.0},
        {"gw": 5, "triple_captain": 5.0},
    ])
    assert choose_chip(4, state, cold_start) is None

    later_is_better = _chip_table([
        {"gw": 10, "triple_captain": 9.0},
        {"gw": 11, "triple_captain": 12.0},
    ])
    assert choose_chip(10, state, later_is_better) is None

    now_is_best = _chip_table([
        {"gw": 10, "triple_captain": 12.0},
        {"gw": 11, "triple_captain": 9.0},
    ])
    assert choose_chip(10, state, now_is_best) == "triple_captain"


def test_chip_policy_reserves_second_set_for_cup_window_or_confirmed_special_gw():
    state = ReplayState({}, bank=0)
    ordinary_gws = _chip_table([
        {"gw": 22, "wildcard": 25.0},
        {"gw": 23, "wildcard": 10.0},
    ])
    assert choose_chip(22, state, ordinary_gws) is None

    known_blank_ahead = _chip_table([
        {"gw": 22, "wildcard": 25.0},
        {"gw": 23, "wildcard": 10.0},
        {"gw": 24, "blank_teams": 6, "schedule_confirmed": True},
    ])
    assert choose_chip(22, state, known_blank_ahead) == "wildcard"

    late_double = _chip_table([
        {"gw": 29, "triple_captain": 12.0, "double_teams": 4, "schedule_confirmed": True},
        {"gw": 30, "triple_captain": 9.0},
    ])
    assert choose_chip(29, state, late_double) == "triple_captain"
