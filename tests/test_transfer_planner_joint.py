import pandas as pd

from fpl_xpts.season_replay import OwnedPlayer, ReplayState
from fpl_xpts.transfer_planner_joint import JointPlannerConfig, plan_transfer_path_joint


def _base_meta():
    positions = ["GKP"] * 2 + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
    return pd.DataFrame({
        "id": list(range(1, 16)),
        "web_name": [f"P{i}" for i in range(1, 16)],
        "position": positions,
        "team": list(range(1, 16)),
        "price_tenths": [50] * 15,
    })


def _state(ft=1):
    return ReplayState(
        squad={i: OwnedPlayer(i, 50) for i in range(1, 16)},
        bank=0,
        free_transfers=ft,
    )


def _origin(meta, gws=(20, 21, 22), default=3.0):
    rows = []
    for gw in gws:
        for pid in meta.id.astype(int):
            rows.append({
                "id": int(pid),
                "gw": int(gw),
                "xpts_mean": float(default),
                "p_play": 1.0,
            })
    return pd.DataFrame(rows)


def test_joint_planner_banks_ft_endogenously_when_no_move_is_useful():
    meta = _base_meta()
    origin = _origin(meta)
    result = plan_transfer_path_joint(
        _state(ft=1),
        meta,
        origin,
        20,
        JointPlannerConfig(weights=(1.0, 0.8, 0.6), time_limit=10.0, mip_rel_gap=0.0),
    )
    assert [a.transfers for a in result.path] == [0, 0, 0]
    assert [a.free_transfers_before for a in result.path] == [1, 2, 3]
    assert [a.free_transfers_after for a in result.path] == [2, 3, 4]


def test_joint_planner_can_take_weak_enabler_leg_to_finance_premium_upgrade():
    meta = _base_meta()
    meta = pd.concat([
        meta,
        pd.DataFrame([
            {
                "id": 16, "web_name": "CheapDEF", "position": "DEF",
                "team": 16, "price_tenths": 40,
            },
            {
                "id": 17, "web_name": "PremiumMID", "position": "MID",
                "team": 17, "price_tenths": 60,
            },
        ])
    ], ignore_index=True)
    origin = _origin(meta, gws=(20,), default=3.0)

    # CheapDEF is individually worse than every owned DEF, but releasing 1.0m
    # makes the huge PremiumMID upgrade affordable. Old fast-local TS v3 could
    # not traverse this negative individual leg.
    origin.loc[origin.id == 16, "xpts_mean"] = 2.0
    origin.loc[origin.id == 17, "xpts_mean"] = 20.0

    result = plan_transfer_path_joint(
        _state(ft=1),
        meta,
        origin,
        20,
        JointPlannerConfig(weights=(1.0,), hit_uncertainty_buffer=1.5,
                           time_limit=10.0, mip_rel_gap=0.0),
    )
    first = result.first_action
    assert first is not None
    assert first.transfers == 2
    assert 16 in first.incoming
    assert 17 in first.incoming
    assert first.official_hit_points == 4


def test_future_hit_cost_is_not_horizon_discounted():
    meta = _base_meta()
    meta = pd.concat([
        meta,
        pd.DataFrame([{
            "id": 16, "web_name": "LaterMID", "position": "MID",
            "team": 16, "price_tenths": 50,
        }])
    ], ignore_index=True)
    origin = _origin(meta, gws=(20, 21), default=3.0)

    # No reason to move in GW20. In GW21 the newcomer improves manager score
    # enough to justify a free transfer, but the test also checks that reported
    # paid-transfer penalties remain literal 4 + buffer rather than weight-scaled.
    origin.loc[(origin.id == 16) & (origin.gw == 20), "xpts_mean"] = 0.0
    origin.loc[(origin.id == 16) & (origin.gw == 21), "xpts_mean"] = 10.0

    result = plan_transfer_path_joint(
        _state(ft=0),
        meta,
        origin,
        20,
        JointPlannerConfig(weights=(1.0, 0.1), hit_uncertainty_buffer=1.5,
                           time_limit=10.0, mip_rel_gap=0.0),
    )
    # Any paid move always carries the full official hit in the action itself.
    for action in result.path:
        paid = max(0, action.transfers - action.free_transfers_before)
        assert action.official_hit_points == 4 * paid
        assert action.uncertainty_penalty == 1.5 * paid


def test_joint_planner_respects_five_transfer_cap():
    meta = _base_meta()
    extras = []
    for j, pid in enumerate(range(16, 21)):
        extras.append({
            "id": pid,
            "web_name": f"X{pid}",
            "position": "MID",
            "team": pid,
            "price_tenths": 50,
        })
    meta = pd.concat([meta, pd.DataFrame(extras)], ignore_index=True)
    origin = _origin(meta, gws=(20,), default=3.0)
    origin.loc[origin.id >= 16, "xpts_mean"] = 50.0

    result = plan_transfer_path_joint(
        _state(ft=1),
        meta,
        origin,
        20,
        JointPlannerConfig(weights=(1.0,), max_transfers_per_week=5,
                           time_limit=10.0, mip_rel_gap=0.0),
    )
    assert result.first_action is not None
    assert 0 <= result.first_action.transfers <= 5
