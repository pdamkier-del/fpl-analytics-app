from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix


POSITION_COUNTS = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
START_MIN = {"GKP": 1, "DEF": 3, "MID": 2, "FWD": 1}
START_MAX = {"GKP": 1, "DEF": 5, "MID": 5, "FWD": 3}


@dataclass
class SquadPlan:
    rows: pd.DataFrame
    expected_score: float


def _best_xi(gwp: pd.DataFrame) -> tuple[list[int], float]:
    goalkeepers = gwp[gwp["position"] == "GKP"].sort_values("xpts_mean", ascending=False)
    start_gk = int(goalkeepers.iloc[0]["id"])
    best_ids: list[int] | None = None
    best_value = -1e9
    for defenders in range(3, 6):
        for midfielders in range(2, 6):
            forwards = 10 - defenders - midfielders
            if forwards < 1 or forwards > 3:
                continue
            selected = [start_gk]
            for position, count in (("DEF", defenders), ("MID", midfielders), ("FWD", forwards)):
                choices = gwp[gwp["position"] == position].nlargest(count, "xpts_mean")
                if len(choices) != count:
                    selected = []
                    break
                selected.extend(choices["id"].astype(int).tolist())
            if not selected:
                continue
            value = float(gwp[gwp["id"].isin(selected)]["xpts_mean"].sum())
            if value > best_value:
                best_value, best_ids = value, selected
    if best_ids is None:
        raise RuntimeError("No valid FPL formation")
    return best_ids, best_value


def _captain_pair(starters: pd.DataFrame) -> tuple[int, int, float]:
    ids = starters["id"].astype(int).to_numpy()
    xpts = starters["xpts_mean"].to_numpy(float)
    pplay = starters["p_play"].to_numpy(float)
    matrix = xpts[:, None] + (1.0 - pplay[:, None]) * xpts[None, :]
    np.fill_diagonal(matrix, -np.inf)
    i, j = np.unravel_index(np.argmax(matrix), matrix.shape)
    return int(ids[i]), int(ids[j]), float(matrix[i, j])


def resolve_squad(players: pd.DataFrame, names: list[str]) -> list[int]:
    result: list[int] = []
    for name in names:
        exact = players[players["web_name"].str.casefold() == name.casefold()]
        if exact.empty:
            exact = players[players["full_name"].str.casefold() == name.casefold()]
        if len(exact) != 1:
            raise ValueError(f"Could not resolve squad player uniquely: {name!r}; matches={exact['web_name'].tolist()}")
        result.append(int(exact.iloc[0]["id"]))
    if len(set(result)) != 15:
        raise ValueError("Squad must resolve to 15 distinct player IDs")
    return result


def _valid_formation(frame: pd.DataFrame) -> bool:
    counts = frame["position"].value_counts().to_dict()
    return all(START_MIN[pos] <= counts.get(pos, 0) <= START_MAX[pos] for pos in START_MIN)


def plan_squad(projections: pd.DataFrame, squad_ids: list[int], gw: int) -> SquadPlan:
    gwp = projections[(projections["gw"] == gw) & (projections["id"].isin(squad_ids))].copy()
    if len(gwp) != 15:
        missing = sorted(set(squad_ids) - set(gwp["id"].astype(int)))
        raise ValueError(f"Expected 15 projected squad players in GW{gw}; missing={missing}")
    goalkeepers = gwp[gwp["position"] == "GKP"].sort_values("xpts_mean", ascending=False)
    best_ids, best_value = _best_xi(gwp)
    starters = gwp[gwp["id"].isin(best_ids)].copy()
    captain, vice, best_captain_value = _captain_pair(starters)
    bench_gk = goalkeepers.iloc[1:]["id"].astype(int).tolist()
    bench_outfield = (
        gwp[(~gwp["id"].isin(best_ids)) & (gwp["position"] != "GKP")]
        .sort_values(["xpts_mean", "p_play"], ascending=False)["id"].astype(int).tolist()
    )
    rows = gwp.copy()
    rows["role"] = "XI"
    rows.loc[rows["id"] == captain, "role"] = "C"
    rows.loc[rows["id"] == vice, "role"] = "VC"
    if bench_gk:
        rows.loc[rows["id"] == bench_gk[0], "role"] = "GK bench"
    for number, player_id in enumerate(bench_outfield, 1):
        rows.loc[rows["id"] == player_id, "role"] = f"Bench {number}"
    order = {"C": 0, "VC": 1, "XI": 2, "Bench 1": 3, "Bench 2": 4, "Bench 3": 5, "GK bench": 6}
    rows["sort"] = rows["role"].map(order)
    rows = rows.sort_values(["sort", "position", "xpts_mean"], ascending=[True, True, False]).drop(columns="sort")
    expected_score = best_value + best_captain_value
    return SquadPlan(rows, expected_score)


def squad_horizon_score(projections: pd.DataFrame, squad_ids: list[int], start_gw: int, horizon: int) -> float:
    score = 0.0
    for gw in range(start_gw, start_gw + horizon):
        gwp = projections[(projections["gw"] == gw) & (projections["id"].isin(squad_ids))]
        ids, xi_value = _best_xi(gwp)
        _captain, _vice, captain_value = _captain_pair(gwp[gwp["id"].isin(ids)])
        score += xi_value + captain_value
    return float(score)


def transfer_options(
    projections: pd.DataFrame,
    players: pd.DataFrame,
    squad_ids: list[int],
    start_gw: int,
    bank: float,
    free_transfers: int,
    horizons: tuple[int, ...] = (1, 3, 5, 6),
    top_n_per_position: int = 8,
) -> pd.DataFrame:
    player_meta = players.set_index("id")
    maximum_horizon = max(horizons)
    horizon_scores = projections[
        (projections["gw"] >= start_gw) & (projections["gw"] < start_gw + maximum_horizon)
    ].groupby("id")["xpts_mean"].sum()
    candidates: set[int] = set()
    for position in POSITION_COUNTS:
        ids = players[players["position"] == position]["id"].astype(int)
        ranked = horizon_scores.reindex(ids).fillna(0.0).sort_values(ascending=False).head(top_n_per_position)
        candidates.update(ranked.index.astype(int).tolist())
    max_horizon = max(horizons)
    baseline_weekly = [squad_horizon_score(projections, squad_ids, start_gw + offset, 1) for offset in range(max_horizon)]
    baseline = {h: float(sum(baseline_weekly[:h])) for h in horizons}
    rows: list[dict[str, Any]] = []
    current_team_counts = players[players["id"].isin(squad_ids)]["team"].value_counts().to_dict()
    for out_id in squad_ids:
        out = player_meta.loc[out_id]
        for in_id in candidates:
            if in_id in squad_ids:
                continue
            incoming = player_meta.loc[in_id]
            if incoming["position"] != out["position"]:
                continue
            if float(incoming["price"]) > float(out["price"]) + bank + 1e-9:
                continue
            if int(incoming["team"]) != int(out["team"]) and current_team_counts.get(int(incoming["team"]), 0) >= 3:
                continue
            new_squad = [in_id if player_id == out_id else player_id for player_id in squad_ids]
            hit = max(0, 1 - free_transfers) * 4
            record: dict[str, Any] = {
                "out": out["web_name"], "in": incoming["web_name"],
                "out_id": out_id, "in_id": in_id,
                "cost": float(incoming["price"]), "money_after": float(out["price"] + bank - incoming["price"]),
                "transfers": 1, "hit": hit,
            }
            weekly = [squad_horizon_score(projections, new_squad, start_gw + offset, 1) for offset in range(max_horizon)]
            for h in horizons:
                gain = float(sum(weekly[:h])) - baseline[h]
                record[f"gain_{h}gw"] = gain
                record[f"net_{h}gw"] = gain - hit
            rows.append(record)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    sort_columns = [f"net_{max(horizons)}gw"]
    if 3 in horizons and max(horizons) != 3:
        sort_columns.append("net_3gw")
    return result.sort_values(sort_columns, ascending=False).reset_index(drop=True)


def roll_transfer_value(
    projections: pd.DataFrame,
    players: pd.DataFrame,
    squad_ids: list[int],
    start_gw: int,
    bank: float,
) -> dict[str, Any]:
    if start_gw + 1 > int(projections["gw"].max()):
        return {"roll_value": 0.0, "plan": "No later projection"}
    first = transfer_options(
        projections, players, squad_ids, start_gw + 1, bank, free_transfers=2,
        horizons=(1, 3, 5), top_n_per_position=7,
    )
    baseline = squad_horizon_score(projections, squad_ids, start_gw + 1, 5)
    best_gain, best_plan = 0.0, "Roll; no transfer needed"
    for _, row in first.head(5).iterrows():
        after_one = [int(row["in_id"]) if x == int(row["out_id"]) else x for x in squad_ids]
        remaining_bank = float(row["money_after"])
        second = transfer_options(
            projections, players, after_one, start_gw + 1, remaining_bank, free_transfers=1,
            horizons=(5,), top_n_per_position=5,
        )
        one_score = squad_horizon_score(projections, after_one, start_gw + 1, 5)
        gain = one_score - baseline
        plan = f"{row['out']} → {row['in']}"
        if not second.empty and float(second.iloc[0]["net_5gw"]) > 0:
            gain += float(second.iloc[0]["net_5gw"])
            plan += f"; {second.iloc[0]['out']} → {second.iloc[0]['in']}"
        if gain > best_gain:
            best_gain, best_plan = gain, plan
    return {"roll_value_from_gw7": best_gain, "plan": best_plan}


def optimize_squad_milp(
    projections: pd.DataFrame,
    players: pd.DataFrame,
    gameweeks: list[int],
    budget: float = 100.0,
    bench_boost: bool = False,
    triple_captain: bool = False,
    candidate_limit_per_position: int = 45,
) -> dict[str, Any]:
    scores = projections[projections["gw"].isin(gameweeks)].pivot_table(
        index="id", columns="gw", values="xpts_mean", aggfunc="sum", fill_value=0.0
    )
    eligible = players[(players["status"] != "u") & (players["id"].isin(scores.index))].copy()
    keep: list[int] = []
    total = scores.sum(axis=1)
    for position in POSITION_COUNTS:
        ids = eligible[eligible["position"] == position]["id"].astype(int)
        keep.extend(total.reindex(ids).fillna(0.0).nlargest(candidate_limit_per_position).index.astype(int).tolist())
    eligible = eligible[eligible["id"].isin(keep)].drop_duplicates("id").reset_index(drop=True)
    n = len(eligible)
    g_count = len(gameweeks)
    y_offset = 0
    z_offset = n
    c_offset = n + n * g_count
    n_vars = n + 2 * n * g_count
    objective = np.zeros(n_vars)
    for gi, gw in enumerate(gameweeks):
        gw_scores = scores.get(gw, pd.Series(dtype=float)).reindex(eligible["id"]).fillna(0.0).to_numpy(float)
        if bench_boost:
            objective[y_offset:y_offset + n] -= gw_scores
        else:
            objective[z_offset + gi * n:z_offset + (gi + 1) * n] -= gw_scores
        captain_multiplier = 2.0 if triple_captain else 1.0
        objective[c_offset + gi * n:c_offset + (gi + 1) * n] -= captain_multiplier * gw_scores

    constraints: list[tuple[np.ndarray, float, float]] = []
    for position, count in POSITION_COUNTS.items():
        row = np.zeros(n_vars); row[:n] = (eligible["position"] == position).astype(float)
        constraints.append((row, count, count))
    for team in eligible["team"].unique():
        row = np.zeros(n_vars); row[:n] = (eligible["team"] == team).astype(float)
        constraints.append((row, -np.inf, 3.0))
    row = np.zeros(n_vars); row[:n] = eligible["price"].to_numpy(float)
    constraints.append((row, -np.inf, budget))
    for gi, _gw in enumerate(gameweeks):
        z_slice = slice(z_offset + gi * n, z_offset + (gi + 1) * n)
        c_slice = slice(c_offset + gi * n, c_offset + (gi + 1) * n)
        row = np.zeros(n_vars); row[z_slice] = 1.0
        constraints.append((row, 11.0, 11.0))
        row = np.zeros(n_vars); row[c_slice] = 1.0
        constraints.append((row, 1.0, 1.0))
        for position in POSITION_COUNTS:
            mask = (eligible["position"] == position).astype(float).to_numpy()
            row = np.zeros(n_vars); row[z_slice] = mask
            constraints.append((row, START_MIN[position], START_MAX[position]))
        for idx in range(n):
            row = np.zeros(n_vars); row[z_offset + gi * n + idx] = 1.0; row[idx] = -1.0
            constraints.append((row, -np.inf, 0.0))
            row = np.zeros(n_vars); row[c_offset + gi * n + idx] = 1.0; row[z_offset + gi * n + idx] = -1.0
            constraints.append((row, -np.inf, 0.0))
    A = lil_matrix((len(constraints), n_vars), dtype=float)
    lower = np.empty(len(constraints)); upper = np.empty(len(constraints))
    for i, (row, lo, hi) in enumerate(constraints):
        nonzero = np.flatnonzero(row)
        A[i, nonzero] = row[nonzero]
        lower[i], upper[i] = lo, hi
    result = milp(
        c=objective, integrality=np.ones(n_vars), bounds=Bounds(0.0, 1.0),
        constraints=LinearConstraint(A.tocsr(), lower, upper), options={"time_limit": 25.0},
    )
    if result.x is None:
        return {"success": False, "message": result.message}
    selected = eligible.loc[result.x[:n] > 0.5, "id"].astype(int).tolist()
    lineups: dict[int, list[int]] = {}
    captains: dict[int, int] = {}
    for gi, gw in enumerate(gameweeks):
        z = result.x[z_offset + gi * n:z_offset + (gi + 1) * n]
        c = result.x[c_offset + gi * n:c_offset + (gi + 1) * n]
        lineups[gw] = eligible.loc[z > 0.5, "id"].astype(int).tolist()
        captains[gw] = int(eligible.loc[np.argmax(c), "id"])
    true_objective = 0.0
    selected_set = set(selected)
    for gw in gameweeks:
        gw_scores = scores.get(gw, pd.Series(dtype=float))
        if bench_boost:
            true_objective += float(gw_scores.reindex(list(selected_set)).fillna(0.0).sum())
        else:
            true_objective += float(gw_scores.reindex(lineups[gw]).fillna(0.0).sum())
        captain_multiplier = 2.0 if triple_captain else 1.0
        true_objective += captain_multiplier * float(gw_scores.get(captains[gw], 0.0))
    return {
        "success": True,
        "objective": true_objective,
        "squad_ids": selected,
        "lineups": lineups,
        "captains": captains,
    }


def chip_values(
    projections: pd.DataFrame,
    players: pd.DataFrame,
    squad_ids: list[int],
    start_gw: int,
    budget: float = 100.0,
) -> pd.DataFrame:
    current = plan_squad(projections, squad_ids, start_gw)
    gwp = projections[(projections["gw"] == start_gw) & (projections["id"].isin(squad_ids))]
    captain = current.rows[current.rows["role"] == "C"].iloc[0]
    bb_score = float(gwp["xpts_mean"].sum() + captain["xpts_mean"])
    tc_score = float(current.expected_score + captain["xpts_mean"])
    free_hit = optimize_squad_milp(projections, players, [start_gw], budget=budget)
    wildcard = optimize_squad_milp(projections, players, list(range(start_gw, start_gw + 6)), budget=budget)
    rows = [
        {"chip": "Bench Boost", "window": f"GW{start_gw}", "projected_score": bb_score, "uplift_vs_current": bb_score - current.expected_score, "opportunity_cost_modelled": False, "recommendation_enabled": False, "status": "experimental"},
        {"chip": "Triple Captain", "window": f"GW{start_gw}", "projected_score": tc_score, "uplift_vs_current": tc_score - current.expected_score, "opportunity_cost_modelled": False, "recommendation_enabled": False, "status": "experimental"},
    ]
    if free_hit.get("success"):
        rows.append({"chip": "Free Hit", "window": f"GW{start_gw}", "projected_score": free_hit["objective"], "uplift_vs_current": free_hit["objective"] - current.expected_score, "opportunity_cost_modelled": False, "recommendation_enabled": False, "status": "experimental"})
    if wildcard.get("success"):
        baseline = squad_horizon_score(projections, squad_ids, start_gw, 6)
        rows.append({"chip": "Wildcard", "window": f"GW{start_gw}-{start_gw+5}", "projected_score": wildcard["objective"], "uplift_vs_current": wildcard["objective"] - baseline, "opportunity_cost_modelled": False, "recommendation_enabled": False, "status": "experimental"})
    return pd.DataFrame(rows)
