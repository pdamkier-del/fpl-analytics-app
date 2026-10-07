import pandas as pd

from fpl_xpts.season_replay import OwnedPlayer, ReplayState
from fpl_xpts.transfer_planner import (
    PlannerConfig,
    PlannerResult,
    TransferAction,
    execute_first_action,
    next_free_transfers,
    plan_transfer_path,
    projected_manager_score,
    transfer_penalties,
)


def _meta(extra=False):
    positions = ["GKP"] * 2 + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
    frame = pd.DataFrame({
        "id": list(range(1, 16)),
        "web_name": [f"P{x}" for x in range(1, 16)],
        "position": positions,
        "team": list(range(1, 16)),
        "price_tenths": [50] * 15,
    })
    if extra:
        frame = pd.concat([frame, pd.DataFrame([{
            "id": 16, "web_name": "NewMID", "position": "MID",
            "team": 16, "price_tenths": 50,
        }])], ignore_index=True)
    return frame


def _state(ft=1):
    return ReplayState(
        {pid: OwnedPlayer(pid, 50) for pid in range(1, 16)},
        bank=0,
        free_transfers=ft,
    )


def _origin(gws=(20, 21, 22), extra=False):
    rows = []
    ids = range(1, 17) if extra else range(1, 16)
    for gw in gws:
        for pid in ids:
            rows.append({
                "id": pid,
                "gw": gw,
                "xpts_mean": 3.0,
                "p_play": 1.0,
            })
    return pd.DataFrame(rows)


def test_ft_transition_is_endogenous_and_capped_at_five():
    assert next_free_transfers(1, 0) == 2
    assert next_free_transfers(2, 0) == 3
    assert next_free_transfers(2, 1) == 2
    assert next_free_transfers(2, 2) == 1
    assert next_free_transfers(2, 3) == 1
    assert next_free_transfers(5, 0) == 5


def test_hit_buffer_only_applies_to_paid_transfers():
    assert transfer_penalties(2, 0, 1.5) == (0, 0.0)
    assert transfer_penalties(2, 2, 1.5) == (0, 0.0)
    assert transfer_penalties(2, 3, 1.5) == (4, 1.5)
    assert transfer_penalties(1, 3, 1.5) == (8, 3.0)


def test_planner_banks_ft_when_no_alternative_players_exist():
    result = plan_transfer_path(
        _state(ft=1),
        _meta(),
        _origin(),
        20,
        PlannerConfig(
            weights=(1.0, 0.8, 0.6),
            beam_width=4,
            candidates_per_transfer_count=1,
            max_transfers_per_week=2,
            milp_time_limit=2.0,
        ),
    )
    assert [x.transfers for x in result.path] == [0, 0, 0]
    assert [x.free_transfers_before for x in result.path] == [1, 2, 3]
    assert [x.free_transfers_after for x in result.path] == [2, 3, 4]


def test_lineup_score_can_bench_now_and_start_same_player_later():
    meta = _meta()
    origin = _origin(gws=(20, 21))
    # P8 is a MID. Make P8 weak now but excellent next GW; the manager-score
    # objective is recomputed separately by GW, so it can be benched then used.
    origin.loc[(origin.id == 8) & (origin.gw == 20), "xpts_mean"] = -5.0
    origin.loc[(origin.id == 8) & (origin.gw == 21), "xpts_mean"] = 20.0
    score_now = projected_manager_score(origin, meta, range(1, 16), 20)
    score_next = projected_manager_score(origin, meta, range(1, 16), 21)
    assert score_next > score_now


def test_execute_first_action_applies_only_current_move_and_ft_state():
    state = _state(ft=2)
    meta = _meta(extra=True)
    action = TransferAction(
        gw=20,
        outgoing=(8,),
        incoming=(16,),
        transfers=1,
        official_hit_points=0,
        uncertainty_penalty=0.0,
        projected_manager_score=60.0,
        utility_this_gw=60.0,
        free_transfers_before=2,
        free_transfers_after=2,
        bank_before=0,
        bank_after=0,
    )
    # A hypothetical later action is included to prove it is not executed.
    later = TransferAction(
        gw=21,
        outgoing=(9,),
        incoming=(8,),
        transfers=1,
        official_hit_points=0,
        uncertainty_penalty=0.0,
        projected_manager_score=60.0,
        utility_this_gw=60.0,
        free_transfers_before=2,
        free_transfers_after=2,
        bank_before=0,
        bank_after=0,
    )
    result = PlannerResult(20, (20, 21), (1.0, 0.8), 100.0, [action, later])
    rows = execute_first_action(state, result, meta)
    assert 16 in state.squad
    assert 8 not in state.squad
    assert 9 in state.squad
    assert state.free_transfers == 2
    assert len(rows) == 1
    assert rows[0]["out_id"] == 8 and rows[0]["in_id"] == 16


def test_fast_score_matches_reference_with_varying_play_probability():
    import numpy as np
    from fpl_xpts.transfer_planner import _build_fast_score_context, _fast_manager_score
    rng = np.random.default_rng(20261005)
    meta = _meta()
    origin = _origin(gws=(20, 21, 22))
    origin['xpts_mean'] = rng.uniform(-2, 15, len(origin))
    origin['p_play'] = rng.uniform(0, 1, len(origin))
    ctx = _build_fast_score_context(origin, meta, [20, 21, 22])
    for gw in (20, 21, 22):
        assert np.isclose(_fast_manager_score(ctx, range(1, 16), gw),
                          projected_manager_score(origin, meta, range(1, 16), gw))


def test_local_search_reaches_five_transfers_with_only_one_ft():
    from fpl_xpts.transfer_planner import _fast_local_candidate_squads
    meta = _meta()
    extra = meta[meta.position == 'MID'].copy()
    extra['id'] += 20
    extra['team'] += 20
    meta = pd.concat([meta, extra], ignore_index=True)
    origin = _origin(gws=(20,))
    new = origin[origin.id.between(8, 12)].copy()
    new['id'] += 20
    new['xpts_mean'] = 15.0
    origin = pd.concat([origin, new], ignore_index=True)
    candidates = _fast_local_candidate_squads(
        _state(ft=1), meta, origin, [20], [1.0], 5, 18, 60, 12)
    assert {len(set(s) - set(range(1, 16))) for s in candidates} == set(range(6))


def test_free_hit_bridge_preserves_permanent_ft_and_forbids_transfers():
    result = plan_transfer_path(
        _state(ft=1),
        _meta(),
        _origin(gws=(20, 21, 22)),
        20,
        PlannerConfig(
            weights=(1.0, 0.8, 0.6),
            free_hit_gw=21,
            beam_width=4,
            max_transfers_per_week=2,
        ),
    )
    assert [a.gw for a in result.path] == [20, 21, 22]
    bridge = next(a for a in result.path if a.gw == 21)
    assert bridge.transfers == 0
    assert bridge.outgoing == ()
    assert bridge.incoming == ()
    assert bridge.free_transfers_before == 2
    assert bridge.free_transfers_after == 2
    assert [a.free_transfers_after for a in result.path] == [2, 2, 3]


def test_fh_aware_ts_can_buy_for_post_fh_run_before_the_bridge():
    from fpl_xpts.fh_transfer_planner import evaluate_fh_aware_path

    meta = _meta(extra=True)
    origin = _origin(gws=(20, 21, 22), extra=True)

    # Owned MID P8 is excellent in the bridge GW but poor afterwards.
    origin.loc[(origin.id == 8) & (origin.gw == 20), "xpts_mean"] = 3.0
    origin.loc[(origin.id == 8) & (origin.gw == 21), "xpts_mean"] = 12.0
    origin.loc[(origin.id == 8) & (origin.gw == 22), "xpts_mean"] = 1.0

    # NewMID is mediocre now, terrible in the bridge GW, but elite afterwards.
    # Ordinary TS should dislike the move; FH-aware TS should be able to buy
    # before GW21 because the permanent squad's GW21 score is skipped.
    origin.loc[(origin.id == 16) & (origin.gw == 20), "xpts_mean"] = 2.0
    origin.loc[(origin.id == 16) & (origin.gw == 21), "xpts_mean"] = -10.0
    origin.loc[(origin.id == 16) & (origin.gw == 22), "xpts_mean"] = 20.0

    config = PlannerConfig(
        weights=(1.0, 1.0, 1.0),
        hit_uncertainty_buffer=1.0,
        beam_width=10,
        top_targets_per_position=18,
        local_bundle_beam=30,
        candidate_return_per_depth=8,
        max_transfers_per_week=2,
    )
    r = evaluate_fh_aware_path(
        _state(ft=1), meta, origin, 20,
        period_end_gw=21, min_fh_gw=21, config=config, allow_fh=True,
    )
    assert r.recommended_fh_gw == 21
    assert r.use_fh_now is False
    assert r.active_result.first_action is not None
    assert 16 in r.active_result.first_action.incoming
    normal = r.normal_result.first_action
    assert normal is not None
    assert 16 not in normal.incoming
