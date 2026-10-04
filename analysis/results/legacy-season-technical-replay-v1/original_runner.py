#!/usr/bin/env python3
"""Run a cutoff-safe 2025/26 FPL squad-management replay.

GW1-5 use the pre-season/prior-season analytic model. GW6-38 use the frozen
rolling v1.0 joint-event forecasts. The squad engine is forecast-provider
agnostic so the Phase 5Q v1.1 reference can replace the signal once rolling
v1.1 forecasts exist for every deadline.
"""
from __future__ import annotations

import json
import os
from itertools import product
from pathlib import Path

import pandas as pd

from fpl_xpts.backtest import _forecast_target, _prep_gws, _prep_prior, _team_summary
from fpl_xpts.data import normalise_name
from fpl_xpts.optimize import optimize_squad_milp, plan_squad
from fpl_xpts.season_replay import (
    OwnedPlayer,
    ReplayState,
    actual_team_points,
    best_normal_transfers,
    initial_squad,
    legalize_team_limit,
    selling_price,
    squad_sale_value,
    valid_squad,
)


ROOT = Path(__file__).resolve().parent
FORECAST_MODE = os.environ.get("FPL_REPLAY_FORECAST", "v1_0")
TRANSFER_POLICY = os.environ.get("FPL_TRANSFER_POLICY", "standard")
CHIP_POLICY = os.environ.get("FPL_CHIP_POLICY", "legacy")
HIT_UNCERTAINTY_BUFFER = float(os.environ.get("FPL_HIT_UNCERTAINTY_BUFFER", "2.0"))
MANUAL_TC_GWS = {
    int(value) for value in os.environ.get("FPL_MANUAL_TC_GWS", "13,33").split(",") if value.strip()
}
MANUAL_EARLY_CHIPS = {
    int(item.split(":", 1)[0]): item.split(":", 1)[1]
    for item in os.environ.get(
        "FPL_MANUAL_EARLY_CHIPS", "2:free_hit,3:wildcard,4:bench_boost"
    ).split(",")
    if item.strip()
}
PHASE5Q_OUTPUTS = {
    "standard": "outputs/v1_1/phase5t_phase5q_season_replay",
    "no_discretionary_hits": "outputs/v1_1/phase5t_phase5q_nohit_replay",
    "simple_3gw": "outputs/v1_1/phase5u_simple_3gw_replay",
}
default_output = (
    "outputs/v1_1/phase5y_hit_buffer_replay"
    if (
        FORECAST_MODE == "phase5q" and TRANSFER_POLICY == "simple_3gw"
        and CHIP_POLICY == "joint_sequence" and MANUAL_EARLY_CHIPS
        and HIT_UNCERTAINTY_BUFFER > 0
    )
    else "outputs/v1_1/phase5x_manual_cold_start_replay"
    if (
        FORECAST_MODE == "phase5q" and TRANSFER_POLICY == "simple_3gw"
        and CHIP_POLICY == "joint_sequence" and MANUAL_EARLY_CHIPS
    )
    else "outputs/v1_1/phase5w_joint_sequence_replay"
    if FORECAST_MODE == "phase5q" and TRANSFER_POLICY == "simple_3gw" and CHIP_POLICY == "joint_sequence"
    else (
        PHASE5Q_OUTPUTS.get(TRANSFER_POLICY, f"outputs/v1_1/phase5t_phase5q_{TRANSFER_POLICY}_replay")
        if FORECAST_MODE == "phase5q" else "outputs/v1_1/phase5s_season_replay"
    )
)
OUT = Path(os.environ.get("FPL_REPLAY_OUT", str(ROOT / default_output)))
SEASON = "2025-26"
PRIOR = "2024-25"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[int, str]]:
    gws = pd.read_csv(ROOT / f"data/cache/history/{SEASON}/gws/merged_gw.csv", low_memory=False)
    gws = gws.drop_duplicates(["element", "GW", "fixture"]).copy()
    gws["position"] = gws["position"].replace({"GK": "GKP"})
    raw = pd.read_csv(ROOT / f"data/cache/history/{SEASON}/players_raw.csv", low_memory=False)
    names = raw.set_index("id")["web_name"].astype(str).to_dict()
    rolling = pd.read_csv(ROOT / "outputs/backtest/rolling_predictions.csv", low_memory=False)
    rolling = rolling[(rolling["backtest_season"] == SEASON)].copy()
    return gws, rolling, names


def load_local_history(season: str) -> dict[str, pd.DataFrame]:
    root = ROOT / f"data/cache/history/{season}"
    return {
        "gws": pd.read_csv(root / "gws/merged_gw.csv", low_memory=False),
        "players": pd.read_csv(root / "players_raw.csv", low_memory=False),
        "teams": pd.read_csv(root / "teams.csv", low_memory=False),
        "fixtures": pd.read_csv(root / "fixtures.csv", low_memory=False),
    }


def early_forecasts(gws: pd.DataFrame, names: dict[int, str]) -> pd.DataFrame:
    season_history = load_local_history(SEASON)
    prior_history = load_local_history(PRIOR)
    season = _prep_gws(season_history["gws"])
    prior_gws = _prep_gws(prior_history["gws"])
    prior_players = _prep_prior(prior_history["players"])
    prior_team = _team_summary(prior_gws)
    teams = season_history["teams"].copy()
    rows = []
    for target_gw in range(1, 6):
        forecast = _forecast_target(
            season, prior_players, prior_team, teams,
            origin_gw=target_gw - 1, target_gw=target_gw,
            tau_minutes=900.0,
        )
        target = gws[gws.GW == target_gw][["element", "name", "team", "position"]].drop_duplicates("element")
        target["name_key"] = target["name"].map(normalise_name)
        forecast = forecast.merge(
            target.rename(columns={"element": "id"})[["id", "name_key", "team", "position"]],
            on=["name_key", "team", "position"], how="inner",
        )
        forecast["gw"] = target_gw
        forecast["origin_gw"] = target_gw - 1
        forecast["xpts_mean"] = forecast["xpts"]
        forecast["p_play"] = (forecast["expected_minutes"] / 75.0).clip(0.01, 0.99)
        forecast["web_name"] = forecast["id"].map(names).fillna(forecast["name"])
        rows.append(forecast[["id", "web_name", "position", "gw", "origin_gw", "xpts_mean", "p_play"]])
    return pd.concat(rows, ignore_index=True)


def gw_meta(gws: pd.DataFrame, names: dict[int, str], gw: int) -> pd.DataFrame:
    frame = gws[gws.GW == gw].sort_values("kickoff_time").drop_duplicates("element", keep="first").copy()
    frame = frame.rename(columns={"element": "id"})
    frame["id"] = frame.id.astype(int)
    frame["price_tenths"] = pd.to_numeric(frame.value, errors="coerce").fillna(0).astype(int)
    frame["web_name"] = frame.id.map(names).fillna(frame.name)
    frame["position"] = frame.position.replace({"GK": "GKP"})
    return frame[["id", "web_name", "team", "position", "price_tenths"]]


def actual_gw(gws: pd.DataFrame, gw: int) -> pd.DataFrame:
    frame = gws[gws.GW == gw].groupby("element", as_index=False).agg(
        points=("total_points", "sum"), minutes=("minutes", "sum")
    )
    return frame.rename(columns={"element": "id"})


def complete_current_projection(origin: pd.DataFrame, meta: pd.DataFrame, gw: int) -> pd.DataFrame:
    current = origin[origin.gw == gw].drop_duplicates("id").copy()
    if "fixtures" not in current:
        current["fixtures"] = 1
    result = meta.merge(current[["id", "xpts_mean", "p_play", "fixtures"]], on="id", how="left")
    result["xpts_mean"] = result.xpts_mean.fillna(0.0)
    result["p_play"] = result.p_play.fillna(0.0)
    result["fixtures"] = result.fixtures.fillna(0).astype(int)
    result["gw"] = gw
    return result


def complete_horizon_projection(origin: pd.DataFrame, meta: pd.DataFrame, gameweeks: list[int]) -> pd.DataFrame:
    return pd.concat(
        [complete_current_projection(origin, meta, target) for target in gameweeks],
        ignore_index=True,
    )


def optimized_ids(origin: pd.DataFrame, meta: pd.DataFrame, gameweeks: list[int], state, effective: bool) -> tuple[list[int], int]:
    players = meta.copy()
    players["status"] = "a"
    if effective:
        effective_prices = {}
        for row in players.itertuples():
            pid = int(row.id)
            if pid in state.squad:
                effective_prices[pid] = selling_price(state.squad[pid].purchase_price, int(row.price_tenths))
            else:
                effective_prices[pid] = int(row.price_tenths)
        players["effective_tenths"] = players.id.map(effective_prices)
        budget_tenths = state.bank + squad_sale_value(state, meta)
    else:
        players["effective_tenths"] = players.price_tenths
        budget_tenths = 1000
    players["price"] = players.effective_tenths / 10.0
    result = optimize_squad_milp(origin, players, gameweeks, budget=budget_tenths / 10.0)
    if not result.get("success"):
        return [], budget_tenths
    return [int(x) for x in result["squad_ids"]], budget_tenths


def chip_opportunities(
    origin: pd.DataFrame,
    meta: pd.DataFrame,
    state,
    gw: int,
) -> pd.DataFrame:
    """Projected chip uplift for this GW and every visible future GW.

    BGWs and DGWs enter through zero/two-fixture player projections.  Archived
    replay schedules are only marked confirmed for the current GW because
    timestamped historical announcement snapshots are unavailable.
    """
    targets = sorted(int(x) for x in origin.gw.unique() if gw <= int(x) <= min(38, gw + 5))
    complete = complete_horizon_projection(origin, meta, targets)
    rows = []
    for target in targets:
        target_projection = complete[complete.gw == target].copy()
        normal = plan_squad(target_projection, list(state.squad), target)
        starters = normal.rows[normal.rows.role.isin(["C", "VC", "XI"])]
        xi_xpts = float(starters.xpts_mean.sum())
        captain_uplift = float(normal.expected_score - xi_xpts)
        all_xpts = float(normal.rows.xpts_mean.sum())
        bench_boost_uplift = all_xpts - xi_xpts

        fh_ids, _ = optimized_ids(target_projection, meta, [target], state, effective=True)
        fh_plan = plan_squad(target_projection, fh_ids, target) if fh_ids else None
        free_hit_uplift = float(fh_plan.expected_score - normal.expected_score) if fh_plan else -999.0

        wc_gws = [x for x in targets if target <= x <= min(38, target + 5)]
        wc_ids, _ = optimized_ids(complete, meta, wc_gws, state, effective=True)
        if wc_ids:
            current_horizon = sum(
                plan_squad(complete[complete.gw == target_gw], list(state.squad), target_gw).expected_score
                for target_gw in wc_gws
            )
            wildcard_horizon = sum(
                plan_squad(complete[complete.gw == target_gw], wc_ids, target_gw).expected_score
                for target_gw in wc_gws
            )
            wildcard_uplift = float(wildcard_horizon - current_horizon)
        else:
            wildcard_uplift = -999.0

        raw_target = origin[origin.gw == target]
        if "fixtures" in raw_target and "team" in raw_target:
            by_team = raw_target.groupby("team")["fixtures"].max()
            all_teams = set(meta.team.dropna())
            blank_teams = len(all_teams - set(by_team.index)) + int(by_team.eq(0).sum())
            double_teams = int(by_team.ge(2).sum())
        else:
            blank_teams = 0
            double_teams = 0
        rows.append({
            "gw": target,
            "triple_captain": captain_uplift,
            "bench_boost": bench_boost_uplift,
            "free_hit": free_hit_uplift,
            "wildcard": wildcard_uplift,
            "blank_teams": blank_teams,
            "double_teams": double_teams,
            "schedule_confirmed": target == gw,
        })
    return pd.DataFrame(rows)


def projected_manager_score(
    projection: pd.DataFrame,
    squad_ids: list[int],
    gw: int,
    bench_boost: bool = False,
    triple_captain: bool = False,
) -> float:
    """Expected manager score for a fixed squad and chip state."""
    plan = plan_squad(projection, squad_ids, gw)
    starters = plan.rows[plan.rows.role.isin(["C", "VC", "XI"])]
    xi_score = float(starters.xpts_mean.sum())
    captain_bonus = float(plan.expected_score - xi_score)
    score = float(plan.rows.xpts_mean.sum()) + captain_bonus if bench_boost else float(plan.expected_score)
    if triple_captain:
        score += captain_bonus
    return score


def chip_available_in_half(state: ReplayState, chip: str, half: int) -> bool:
    return not any((used <= 19) == (half == 1) for used in state.chips_used[chip])


def joint_chip_sequence(
    origin: pd.DataFrame,
    meta: pd.DataFrame,
    state: ReplayState,
    gw: int,
) -> dict:
    """Optimize FH/WC/BB jointly over the visible window; execute only this GW."""
    half = 1 if gw <= 19 else 2
    half_end = 19 if half == 1 else 38
    targets = sorted(int(x) for x in origin.gw.unique() if gw <= int(x) <= min(half_end, gw + 5))
    if not targets:
        targets = [gw]
    complete = complete_horizon_projection(origin, meta, targets)
    manual_tc_targets = {
        target for target in targets
        if target in MANUAL_TC_GWS and chip_available_in_half(state, "triple_captain", half)
    }
    available = [
        chip for chip in ("wildcard", "free_hit", "bench_boost")
        if chip_available_in_half(state, chip, half)
    ]

    allowed = [target for target in targets if target > 5 and target not in manual_tc_targets]
    if half == 2 and gw < 28:
        current_rows = origin[origin.gw == gw]
        fixture_by_team = current_rows.groupby("team")["fixtures"].max() if not current_rows.empty else pd.Series(dtype=float)
        blank_teams = len(set(meta.team.dropna()) - set(fixture_by_team.index)) + int(fixture_by_team.eq(0).sum())
        double_teams = int(fixture_by_team.ge(2).sum())
        special_now = blank_teams >= 4 or double_teams >= 2
        allowed = [target for target in allowed if target >= 28 or (target == gw and special_now)]

    base_ids = list(state.squad)
    score_cache: dict[tuple[tuple[int, ...], int, bool, bool], float] = {}

    def score(ids: list[int], target: int, bb: bool = False, tc: bool = False) -> float:
        key = (tuple(sorted(ids)), target, bb, tc)
        if key not in score_cache:
            score_cache[key] = projected_manager_score(complete, ids, target, bb, tc)
        return score_cache[key]

    fh_ids: dict[int, list[int]] = {}
    if "free_hit" in available:
        for target in allowed:
            ids, _ = optimized_ids(complete[complete.gw == target], meta, [target], state, effective=True)
            if ids:
                fh_ids[target] = ids

    wc_ids: dict[int, list[int]] = {}
    wc_resources: dict[int, int] = {}
    if "wildcard" in available:
        for target in allowed:
            horizon = [future for future in targets if future >= target]
            ids, resources = optimized_ids(complete, meta, horizon, state, effective=True)
            if ids:
                wc_ids[target] = ids
                wc_resources[target] = resources

    chip_targets = {
        "wildcard": [target for target in allowed if target in wc_ids],
        "free_hit": [target for target in allowed if target in fh_ids],
        "bench_boost": allowed,
    }
    terminal_values = {"wildcard": 12.0, "free_hit": 10.0, "bench_boost": 10.0}
    best: dict | None = None
    choices = [[None] + chip_targets[chip] for chip in available]
    for assignments in product(*choices) if choices else [()]:
        sequence = dict(zip(available, assignments))
        used_weeks = [target for target in assignments if target is not None]
        if len(used_weeks) != len(set(used_weeks)):
            continue
        total_score = 0.0
        wc_target = sequence.get("wildcard")
        for target in targets:
            ids = wc_ids[wc_target] if wc_target is not None and target >= wc_target else base_ids
            tc = target in manual_tc_targets
            if sequence.get("free_hit") == target:
                total_score += score(fh_ids[target], target)
            else:
                total_score += score(ids, target, sequence.get("bench_boost") == target, tc)
        if max(targets) < half_end:
            total_score += sum(terminal_values[chip] for chip in available if sequence.get(chip) is None)
        used_count = sum(target is not None for target in assignments)
        rank = (total_score, -used_count)
        if best is None or rank > best["rank"]:
            best = {"rank": rank, "score": total_score, "sequence": sequence}

    sequence = best["sequence"] if best else {}
    current_chip = next((chip for chip, target in sequence.items() if target == gw), None)
    if current_chip is None and gw in manual_tc_targets:
        current_chip = "triple_captain"
    labels = {"wildcard": "WC", "free_hit": "FH", "bench_boost": "BB"}
    sequence_text = ", ".join(
        f"{labels[chip]}:{'save' if sequence.get(chip) is None else 'GW' + str(sequence[chip])}"
        for chip in available
    )
    return {
        "chip": current_chip,
        "fh_ids": fh_ids.get(gw, []),
        "wc_ids": wc_ids.get(gw, []),
        "wc_resources": wc_resources.get(gw, 0),
        "sequence": sequence_text,
        "sequence_score": float(best["score"]) if best else 0.0,
    }


def checkpoint_paths() -> tuple[Path, Path, Path]:
    return OUT / "checkpoint_state.json", OUT / "checkpoint_gameweek_log.csv", OUT / "checkpoint_squads.csv"


def save_checkpoint(
    gw: int,
    state: ReplayState,
    initial_ids: list[int],
    logs: list[dict],
    squad_logs: list[dict],
    total: int,
    no_transfer_total: int,
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    state_path, log_path, squads_path = checkpoint_paths()
    payload = {
        "last_completed_gw": gw,
        "squad": {str(pid): owned.purchase_price for pid, owned in state.squad.items()},
        "bank": state.bank,
        "free_transfers": state.free_transfers,
        "chips_used": state.chips_used,
        "initial_ids": initial_ids,
        "total": total,
        "no_transfer_total": no_transfer_total,
        "forecast_mode": FORECAST_MODE,
        "transfer_policy": TRANSFER_POLICY,
        "chip_policy": CHIP_POLICY,
        "manual_early_chips": MANUAL_EARLY_CHIPS,
        "hit_uncertainty_buffer": HIT_UNCERTAINTY_BUFFER,
    }
    temp_state = state_path.with_suffix(".tmp")
    temp_state.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temp_state.replace(state_path)
    pd.DataFrame(logs).to_csv(log_path, index=False)
    pd.DataFrame(squad_logs).to_csv(squads_path, index=False)


def load_checkpoint() -> tuple[int, ReplayState, list[int], list[dict], list[dict], int, int] | None:
    state_path, log_path, squads_path = checkpoint_paths()
    if os.environ.get("FPL_REPLAY_RESUME", "0") != "1" or not state_path.exists():
        return None
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    expected = (
        FORECAST_MODE, TRANSFER_POLICY, CHIP_POLICY,
        MANUAL_EARLY_CHIPS, HIT_UNCERTAINTY_BUFFER,
    )
    stored_manual = {int(gw): chip for gw, chip in payload.get("manual_early_chips", {}).items()}
    actual = (
        payload.get("forecast_mode"), payload.get("transfer_policy"),
        payload.get("chip_policy"), stored_manual,
        float(payload.get("hit_uncertainty_buffer", 0.0)),
    )
    if actual != expected:
        raise RuntimeError(f"Checkpoint configuration {actual} does not match requested {expected}")
    squad = {int(pid): OwnedPlayer(int(pid), int(price)) for pid, price in payload["squad"].items()}
    state = ReplayState(
        squad=squad,
        bank=int(payload["bank"]),
        free_transfers=int(payload["free_transfers"]),
        chips_used={key: [int(x) for x in values] for key, values in payload["chips_used"].items()},
    )
    logs = pd.read_csv(log_path).to_dict("records") if log_path.exists() else []
    squad_logs = pd.read_csv(squads_path).to_dict("records") if squads_path.exists() else []
    return (
        int(payload["last_completed_gw"]), state, [int(x) for x in payload["initial_ids"]],
        logs, squad_logs, int(payload["total"]), int(payload["no_transfer_total"]),
    )


def main() -> None:
    gws, rolling, names = load_inputs()
    if FORECAST_MODE == "phase5q":
        forecast = pd.read_csv(
            ROOT / "outputs/v1_1/phase5t_rolling_reference/rolling_phase5q_forecasts.csv",
            low_memory=False,
        )[["id", "web_name", "position", "gw", "origin_gw", "xpts_mean", "p_play", "fixtures"]]
    else:
        early = early_forecasts(gws, names)
        forecast = pd.concat([
            early,
            rolling[["id", "web_name", "position", "gw", "origin_gw", "xpts_mean", "p_play"]],
        ], ignore_index=True)
        forecast["fixtures"] = 1
    forecast["id"] = forecast.id.astype(int)

    meta1 = gw_meta(gws, names, 1)
    known_meta = meta1.copy()
    checkpoint = load_checkpoint()
    if checkpoint:
        last_gw, state, initial_ids, logs, squad_logs, total, no_transfer_total = checkpoint
        for historical_gw in range(2, last_gw + 1):
            observed = gw_meta(gws, names, historical_gw)
            known_meta = pd.concat([
                known_meta[~known_meta.id.isin(observed.id)], observed
            ], ignore_index=True).drop_duplicates("id", keep="last")
        start_gw = last_gw + 1
        print(f"Resuming after GW{last_gw}; next is GW{start_gw}", flush=True)
    else:
        origin1 = complete_current_projection(forecast[forecast.origin_gw == 0], meta1, 1)
        state = initial_squad(origin1, meta1, [1])
        initial_ids = list(state.squad)
        logs = []
        squad_logs = []
        total = 0
        no_transfer_total = 0
        start_gw = 1

    stop_after = int(os.environ.get("FPL_REPLAY_STOP_AFTER_GW", "38"))
    for gw in range(start_gw, 39):
        observed_meta = gw_meta(gws, names, gw)
        known_meta = pd.concat([
            known_meta[~known_meta.id.isin(observed_meta.id)], observed_meta
        ], ignore_index=True).drop_duplicates("id", keep="last")
        meta = known_meta.copy()
        origin = forecast[forecast.origin_gw == gw - 1].copy()
        current = complete_current_projection(origin, meta, gw)
        # Ensure later horizon rows carry current metadata for optimization.
        origin = origin.merge(meta[["id", "team", "price_tenths"]], on="id", how="left")
        selected = meta[meta.id.isin(state.squad)]
        structural_ok = (
            len(selected) == 15
            and selected.id.nunique() == 15
            and selected.position.value_counts().to_dict() == {"MID": 5, "DEF": 5, "FWD": 3, "GKP": 2}
        )
        if not structural_ok:
            raise RuntimeError(
                f"GW{gw}: structurally invalid managed squad before decisions; "
                f"n={len(selected)}, positions={selected.position.value_counts().to_dict()}, "
                f"teams={selected.team.value_counts().head().to_dict()}"
            )

        sequence_text = ""
        sequence_score = 0.0
        if CHIP_POLICY == "joint_sequence":
            decision = joint_chip_sequence(origin, meta, state, gw)
            chip = MANUAL_EARLY_CHIPS.get(gw, decision["chip"])
            sequence_text = decision["sequence"]
            sequence_score = decision["sequence_score"]
        else:
            from fpl_xpts.season_replay import choose_chip
            opportunities = chip_opportunities(origin, meta, state, gw)
            chip = choose_chip(gw, state, opportunities)
        fh_ids: list[int] = []
        wc_ids: list[int] = []
        resources = 0
        if CHIP_POLICY == "joint_sequence" and chip == "free_hit":
            fh_ids = decision["fh_ids"]
            if not fh_ids:
                fh_ids, resources = optimized_ids(current, meta, [gw], state, effective=True)
        elif CHIP_POLICY == "joint_sequence" and chip == "wildcard":
            wc_ids = decision["wc_ids"]
            resources = decision["wc_resources"]
            if not wc_ids:
                horizon_gws = sorted(int(x) for x in origin.gw.unique() if gw <= int(x) <= min(38, gw + 5))
                complete_origin = complete_horizon_projection(origin, meta, horizon_gws or [gw])
                wc_ids, resources = optimized_ids(complete_origin, meta, horizon_gws or [gw], state, effective=True)
        elif chip == "free_hit":
            fh_ids, resources = optimized_ids(current, meta, [gw], state, effective=True)
        elif chip == "wildcard":
            horizon_gws = sorted(int(x) for x in origin.gw.unique() if gw <= int(x) <= min(38, gw + 5))
            complete_origin = complete_horizon_projection(origin, meta, horizon_gws or [gw])
            wc_ids, resources = optimized_ids(complete_origin, meta, horizon_gws or [gw], state, effective=True)

        transfers = []
        hit_cost = 0
        scoring_squad = list(state.squad)
        if chip == "free_hit" and fh_ids:
            scoring_squad = fh_ids
        elif chip == "wildcard" and wc_ids:
            old_squad = state.squad.copy()
            effective_cost = 0
            new_squad = {}
            prices = meta.set_index("id").price_tenths.astype(int)
            for pid in wc_ids:
                if pid in old_squad:
                    owned = old_squad[pid]
                    effective_cost += selling_price(owned.purchase_price, int(prices[pid]))
                    new_squad[pid] = owned
                else:
                    effective_cost += int(prices[pid])
                    new_squad[pid] = OwnedPlayer(pid, int(prices[pid]))
            state.bank = resources - effective_cost
            state.squad = new_squad
            scoring_squad = list(state.squad)
        elif gw > 1:
            transfers = legalize_team_limit(state, meta, origin, gw)
            remaining_cap = max(0, 5-len(transfers))
            if TRANSFER_POLICY == "no_discretionary_hits":
                remaining_cap = min(remaining_cap, max(0, state.free_transfers-len(transfers)))
            transfers += best_normal_transfers(
                state, meta, origin, gw, transfers_already=len(transfers),
                max_total_transfers=remaining_cap,
                transfer_policy=TRANSFER_POLICY,
                hit_uncertainty_buffer=HIT_UNCERTAINTY_BUFFER,
            )
            hit_cost = sum(int(row["hit"]) for row in transfers)
            scoring_squad = list(state.squad)

        if chip != "free_hit" and not valid_squad(meta, state.squad):
            raise RuntimeError(f"GW{gw}: managed squad remains invalid after decisions")

        if chip:
            state.chips_used[chip].append(gw)
        plan = plan_squad(current, scoring_squad, gw)
        score, autosubs = actual_team_points(plan.rows, actual_gw(gws, gw), chip, hit_cost)
        total += score
        control_plan = plan_squad(current, initial_ids, gw)
        control_score, _ = actual_team_points(control_plan.rows, actual_gw(gws, gw), None, 0)
        no_transfer_total += control_score

        used = len(transfers)
        if chip in ("wildcard", "free_hit"):
            state.free_transfers = min(5, state.free_transfers + 1)
        else:
            state.free_transfers = min(5, max(0, state.free_transfers - used) + 1)

        captain_id = int(plan.rows.loc[plan.rows.role == "C", "id"].iloc[0])
        logs.append({
            "gw": gw, "score": score, "cumulative": total, "chip": chip or "",
            "transfers": used, "hit_cost": hit_cost, "free_transfers_next": state.free_transfers,
            "bank": state.bank / 10.0, "captain": names.get(captain_id, str(captain_id)),
            "autosubs": ",".join(map(str, autosubs)),
            "transfer_moves": "; ".join(f"{x['out']} -> {x['in']}" for x in transfers),
            "projected_transfer_gain": sum(float(x["gain"]) for x in transfers),
            "projected_transfer_net_gain": sum(float(x.get("net_gain", x["gain"] - x["hit"])) for x in transfers),
            "forecast_source": (
                ("Phase 5Q cold start" if gw <= 5 else "rolling Phase 5Q/v1.1")
                if FORECAST_MODE == "phase5q"
                else ("prior-season analytic" if gw <= 5 else "frozen rolling joint-event v1.0")
            ),
            "no_transfer_control_score": control_score,
            "no_transfer_control_cumulative": no_transfer_total,
            "chip_sequence_plan": sequence_text,
            "chip_sequence_projected_score": sequence_score,
        })
        for row in plan.rows.itertuples():
            squad_logs.append({
                "gw": gw, "id": int(row.id), "name": str(row.web_name),
                "position": str(row.position), "role": str(row.role),
                "xpts": float(row.xpts_mean),
            })
        save_checkpoint(gw, state, initial_ids, logs, squad_logs, total, no_transfer_total)
        print(f"GW{gw} complete: {score} pts, cumulative {total}", flush=True)
        if gw >= stop_after:
            print(f"Stopped after GW{gw}; checkpoint saved", flush=True)
            break

    OUT.mkdir(parents=True, exist_ok=True)
    log = pd.DataFrame(logs)
    log.to_csv(OUT / "gameweek_log.csv", index=False)
    pd.DataFrame(squad_logs).to_csv(OUT / "squads_and_lineups.csv", index=False)
    summary = {
        "season": SEASON,
        "gameweeks": [1, 38],
        "total_points": int(total),
        "transfers": int(log.transfers.sum()),
        "hit_points": int(log.hit_cost.sum()),
        "chips": state.chips_used,
        "final_bank": float(state.bank / 10.0),
        "no_transfer_control_points": int(no_transfer_total),
        "uplift_vs_no_transfer_control": int(total - no_transfer_total),
        "transfer_policy": TRANSFER_POLICY,
        "chip_policy": CHIP_POLICY,
        "manual_triple_captain_gws": sorted(MANUAL_TC_GWS),
        "manual_early_chips": {str(gw): chip for gw, chip in sorted(MANUAL_EARLY_CHIPS.items())},
        "hit_uncertainty_buffer": HIT_UNCERTAINTY_BUFFER,
        "transfer_rule": (
            f"jointly optimize legal bundles of zero to five transfers over the rolling unweighted current GW plus next 2 GWs; hits cost 4 plus a {HIT_UNCERTAINTY_BUFFER:.2f}-point uncertainty buffer, bankable free transfers carry 2.16-point option value, and an expiring FT at the five-FT cap costs 0"
            if TRANSFER_POLICY == "simple_3gw" else
            "legacy discounted six-GW greedy transfer rule"
        ),
        "forecast_sources": (
            {"GW1-5": "Phase 5Q event model with previous-season cold-start state",
             "GW6-38": "rolling deadline-frozen Phase 5Q/v1.1, six-GW horizons"}
            if FORECAST_MODE == "phase5q" else
            {"GW1-5": "prior-season analytic model",
             "GW6-38": "frozen rolling joint-event v1.0 forecasts"}
        ),
        "period_points": {
            "GW1-5_cold_start": int(log.loc[log.gw.between(1, 5), "score"].sum()),
            "GW6-21_development_assisted": int(log.loc[log.gw.between(6, 21), "score"].sum()),
            "GW22-38_later_temporal_validation": int(log.loc[log.gw.between(22, 38), "score"].sum()),
        },
        "status": (
            "Phase 5Q rolling replay; GW1-5 cold start, schedule-snapshot and DC-development caveats apply"
            if FORECAST_MODE == "phase5q" else
            "decision-engine validation; not Phase 5Q v1.1 performance"
        ),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
