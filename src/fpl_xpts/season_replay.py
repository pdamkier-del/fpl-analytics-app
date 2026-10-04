from __future__ import annotations

from dataclasses import dataclass, field
from math import floor
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp

from .optimize import POSITION_COUNTS, START_MAX, START_MIN, optimize_squad_milp, plan_squad


@dataclass
class OwnedPlayer:
    player_id: int
    purchase_price: int  # tenths of a million


@dataclass
class ReplayState:
    squad: dict[int, OwnedPlayer]
    bank: int
    free_transfers: int = 1
    chips_used: dict[str, list[int]] = field(default_factory=lambda: {
        "wildcard": [], "free_hit": [], "bench_boost": [], "triple_captain": []
    })


def selling_price(purchase_price: int, current_price: int) -> int:
    """Official FPL sale value in integer tenths."""
    if current_price <= purchase_price:
        return current_price
    return purchase_price + floor((current_price - purchase_price) / 2)


def valid_squad(meta: pd.DataFrame, ids: Iterable[int]) -> bool:
    selected = meta[meta["id"].isin(list(ids))]
    if len(selected) != 15 or selected["id"].nunique() != 15:
        return False
    counts = selected["position"].value_counts().to_dict()
    if any(counts.get(position, 0) != count for position, count in POSITION_COUNTS.items()):
        return False
    return bool((selected.groupby("team").size() <= 3).all())


def squad_sale_value(state: ReplayState, meta: pd.DataFrame) -> int:
    prices = meta.set_index("id")["price_tenths"].to_dict()
    return sum(
        selling_price(owned.purchase_price, int(prices[player_id]))
        for player_id, owned in state.squad.items()
    )


def horizon_values(
    origin: pd.DataFrame,
    current_gw: int,
    weights: tuple[float, ...] = (1.00, 0.85, 0.70, 0.55, 0.40, 0.25),
) -> pd.Series:
    """Return each player's summed forecast over the requested rolling horizon."""
    weight_by_offset = dict(enumerate(weights))
    frame = origin[origin["gw"].between(current_gw, current_gw + len(weights) - 1)].copy()
    frame["weighted"] = [
        float(x) * weight_by_offset.get(int(gw) - current_gw, 0.0)
        for x, gw in zip(frame["xpts_mean"], frame["gw"])
    ]
    return frame.groupby("id")["weighted"].sum()


def _transfer_costs(
    state: ReplayState,
    count: int,
    transfers_already: int,
    saved_ft_value: float,
    hit_uncertainty_buffer: float,
) -> list[tuple[int, float]]:
    costs = []
    for offset in range(1, count + 1):
        transfer_index = transfers_already + offset
        hit = 4 if transfer_index > state.free_transfers else 0
        expiring_ft = state.free_transfers >= 5 and transfer_index == 1
        decision_cost = (
            float(hit) + hit_uncertainty_buffer
            if hit else (0.0 if expiring_ft else saved_ft_value)
        )
        costs.append((hit, decision_cost))
    return costs


def _best_joint_3gw_transfer_bundle(
    state: ReplayState,
    meta: pd.DataFrame,
    origin: pd.DataFrame,
    gw: int,
    max_total_transfers: int,
    transfers_already: int,
    saved_ft_value: float,
    hit_uncertainty_buffer: float,
) -> list[dict[str, float | int | str]]:
    """Optimize one legal simultaneous bundle of zero to five transfers."""
    values = horizon_values(origin, gw, weights=(1.0, 1.0, 1.0))
    owned_ids = set(state.squad)
    eligible_ids = set(origin.id.astype(int)) | owned_ids
    players = meta[meta.id.isin(eligible_ids)].drop_duplicates("id").copy().reset_index(drop=True)
    if not owned_ids.issubset(set(players.id.astype(int))):
        raise RuntimeError(f"GW{gw}: joint transfer optimizer is missing an owned player")

    players["value"] = players.id.map(values).fillna(0.0).astype(float)
    current_prices = players.set_index("id").price_tenths.astype(int).to_dict()
    sale_prices = {
        player_id: selling_price(owned.purchase_price, int(current_prices[player_id]))
        for player_id, owned in state.squad.items()
    }
    players["owned"] = players.id.isin(owned_ids)
    players["effective_price"] = [
        sale_prices[int(row.id)] if bool(row.owned) else int(row.price_tenths)
        for row in players.itertuples()
    ]
    resources = int(state.bank + sum(sale_prices.values()))
    current_value = float(values.reindex(list(owned_ids)).fillna(0.0).sum())
    n = len(players)

    constraint_rows = []
    lower = []
    upper = []
    for position, count in POSITION_COUNTS.items():
        constraint_rows.append((players.position == position).to_numpy(float))
        lower.append(float(count)); upper.append(float(count))
    for team in players.team.dropna().unique():
        constraint_rows.append((players.team == team).to_numpy(float))
        lower.append(-np.inf); upper.append(3.0)
    constraint_rows.append(players.effective_price.to_numpy(float))
    lower.append(-np.inf); upper.append(float(resources))
    incoming = (~players.owned).to_numpy(float)

    best = None
    maximum_new = min(max_total_transfers, max(0, 5 - transfers_already))
    for transfer_count in range(1, maximum_new + 1):
        rows = constraint_rows + [incoming]
        lo = lower + [float(transfer_count)]
        hi = upper + [float(transfer_count)]
        result = milp(
            c=-players.value.to_numpy(float),
            integrality=np.ones(n),
            bounds=Bounds(0.0, 1.0),
            constraints=LinearConstraint(np.vstack(rows), np.array(lo), np.array(hi)),
            options={"time_limit": 10.0},
        )
        if result.x is None:
            continue
        selected = set(players.loc[result.x > 0.5, "id"].astype(int))
        if len(selected) != 15:
            continue
        gain = float(values.reindex(list(selected)).fillna(0.0).sum() - current_value)
        costs = _transfer_costs(
            state, transfer_count, transfers_already,
            saved_ft_value, hit_uncertainty_buffer,
        )
        decision_cost = float(sum(cost for _hit, cost in costs))
        net_gain = gain - decision_cost
        if net_gain <= 0:
            continue
        if best is None or net_gain > best["net_gain"] + 1e-9:
            best = {
                "selected": selected,
                "count": transfer_count,
                "gain": gain,
                "net_gain": net_gain,
                "costs": costs,
            }

    if best is None:
        return []

    selected = best["selected"]
    outgoing_ids = owned_ids - selected
    incoming_ids = selected - owned_ids
    by_id = players.set_index("id")
    pairs = []
    for position in POSITION_COUNTS:
        outs = sorted(
            [pid for pid in outgoing_ids if by_id.loc[pid, "position"] == position],
            key=lambda pid: float(values.get(pid, 0.0)),
        )
        ins = sorted(
            [pid for pid in incoming_ids if by_id.loc[pid, "position"] == position],
            key=lambda pid: float(values.get(pid, 0.0)),
            reverse=True,
        )
        if len(outs) != len(ins):
            raise RuntimeError(f"GW{gw}: joint transfer bundle cannot pair {position} moves")
        for out_id, in_id in zip(outs, ins):
            gain = float(values.get(in_id, 0.0) - values.get(out_id, 0.0))
            pairs.append((gain, out_id, in_id))
    pairs.sort(reverse=True)

    final_spend = int(players.loc[players.id.isin(selected), "effective_price"].sum())
    final_bank = resources - final_spend
    for out_id in outgoing_ids:
        state.squad.pop(out_id)
    for in_id in incoming_ids:
        state.squad[in_id] = OwnedPlayer(in_id, int(by_id.loc[in_id, "price_tenths"]))
    state.bank = final_bank

    transfers = []
    for index, ((gain, out_id, in_id), (hit, decision_cost)) in enumerate(
        zip(pairs, best["costs"]), 1
    ):
        transfers.append({
            "out_id": int(out_id), "in_id": int(in_id),
            "out": str(by_id.loc[out_id, "web_name"]),
            "in": str(by_id.loc[in_id, "web_name"]),
            "gain": gain, "hit": hit, "decision_cost": decision_cost,
            "net_gain": gain - decision_cost,
            "horizon_gws": 3,
            "sale_price": sale_prices[out_id],
            "buy_price": int(by_id.loc[in_id, "price_tenths"]),
            "bank_after": final_bank,
            "bundle_size": int(best["count"]),
            "bundle_gain": float(best["gain"]),
            "bundle_net_gain": float(best["net_gain"]),
        })
    return transfers


def best_normal_transfers(
    state: ReplayState,
    meta: pd.DataFrame,
    origin: pd.DataFrame,
    gw: int,
    minimum_gain: float = 0.35,
    hit_buffer: float = 0.75,
    max_total_transfers: int = 5,
    transfers_already: int = 0,
    transfer_policy: str = "standard",
    saved_ft_value: float = 2.16,
    hit_uncertainty_buffer: float = 2.0,
) -> list[dict[str, float | int | str]]:
    """Cutoff-safe transfer policy.

    ``simple_3gw`` compares the unweighted forecast for the current GW plus
    the next two GWs. Hits cost 4 points plus a forecast-uncertainty buffer.
    A bankable free transfer carries its measured option value; the first free
    transfer at the five-FT cap carries no option cost because it would
    otherwise expire.
    """
    simple_3gw = transfer_policy == "simple_3gw"
    if simple_3gw and len(state.squad) == 15:
        return _best_joint_3gw_transfer_bundle(
            state, meta, origin, gw, max_total_transfers,
            transfers_already, saved_ft_value, hit_uncertainty_buffer,
        )
    values = horizon_values(origin, gw, weights=(1.0, 1.0, 1.0) if simple_3gw else (
        1.00, 0.85, 0.70, 0.55, 0.40, 0.25
    ))
    player_meta = meta.drop_duplicates("id").set_index("id")
    squad_ids = list(state.squad)
    bank = state.bank
    transfers: list[dict[str, float | int | str]] = []
    for transfer_number in range(1, max_total_transfers + 1):
        best = None
        team_counts = player_meta.loc[squad_ids, "team"].value_counts().to_dict()
        for out_id in squad_ids:
            out = player_meta.loc[out_id]
            sale = selling_price(
                state.squad[out_id].purchase_price,
                int(out["price_tenths"]),
            )
            candidates = meta[
                (meta["position"] == out["position"])
                & (~meta["id"].isin(squad_ids))
                & (meta["price_tenths"] <= sale + bank)
            ]
            for incoming in candidates.itertuples():
                if incoming.team != out["team"] and team_counts.get(incoming.team, 0) >= 3:
                    continue
                gain = float(values.get(int(incoming.id), 0.0) - values.get(int(out_id), 0.0))
                transfer_index = transfers_already + transfer_number
                hit = 4 if transfer_index > state.free_transfers else 0
                if simple_3gw:
                    expiring_ft = state.free_transfers >= 5 and transfer_index == 1
                    decision_cost = (
                        float(hit) + hit_uncertainty_buffer
                        if hit else (0.0 if expiring_ft else saved_ft_value)
                    )
                    required = decision_cost
                else:
                    decision_cost = float(hit)
                    required = minimum_gain + (hit + hit_buffer if hit else 0.0)
                if gain <= required:
                    continue
                record = {
                    "out_id": int(out_id), "in_id": int(incoming.id),
                    "out": str(out["web_name"]), "in": str(incoming.web_name),
                    "gain": gain, "hit": hit, "decision_cost": decision_cost,
                    "net_gain": gain - decision_cost,
                    "horizon_gws": 3 if simple_3gw else 6,
                    "sale_price": sale,
                    "buy_price": int(incoming.price_tenths),
                }
                if best is None or record["net_gain"] > best["net_gain"]:
                    best = record
        if best is None:
            break
        out_id, in_id = int(best["out_id"]), int(best["in_id"])
        bank += int(best["sale_price"]) - int(best["buy_price"])
        state.squad.pop(out_id)
        state.squad[in_id] = OwnedPlayer(in_id, int(best["buy_price"]))
        squad_ids = list(state.squad)
        best["bank_after"] = bank
        transfers.append(best)
    state.bank = bank
    return transfers


def legalize_team_limit(
    state: ReplayState,
    meta: pd.DataFrame,
    origin: pd.DataFrame,
    gw: int,
) -> list[dict[str, float | int | str]]:
    """Resolve a four-player club created by a real-life club transfer.

    The move is mandatory, so the least damaging affordable same-position
    replacement is selected even when its projected gain is negative.
    """
    values = horizon_values(origin, gw)
    player_meta = meta.drop_duplicates("id").set_index("id")
    moves: list[dict[str, float | int | str]] = []
    while True:
        squad_ids = list(state.squad)
        counts = player_meta.loc[squad_ids, "team"].value_counts()
        excess = counts[counts > 3]
        if excess.empty:
            break
        club = excess.index[0]
        best = None
        for out_id in [pid for pid in squad_ids if player_meta.loc[pid, "team"] == club]:
            out = player_meta.loc[out_id]
            sale = selling_price(state.squad[out_id].purchase_price, int(out.price_tenths))
            team_counts = player_meta.loc[squad_ids, "team"].value_counts().to_dict()
            candidates = meta[
                (meta.position == out.position)
                & (~meta.id.isin(squad_ids))
                & (meta.price_tenths <= sale + state.bank)
            ]
            for incoming in candidates.itertuples():
                if team_counts.get(incoming.team, 0) >= 3:
                    continue
                gain = float(values.get(int(incoming.id), 0.0) - values.get(int(out_id), 0.0))
                hit = 4 if len(moves) + 1 > state.free_transfers else 0
                record = {
                    "out_id": int(out_id), "in_id": int(incoming.id),
                    "out": str(out.web_name), "in": str(incoming.web_name),
                    "gain": gain, "hit": hit, "sale_price": sale,
                    "buy_price": int(incoming.price_tenths), "forced": True,
                }
                if best is None or (gain - hit) > (best["gain"] - best["hit"]):
                    best = record
        if best is None:
            raise RuntimeError(f"GW{gw}: cannot legalize club limit for {club}")
        out_id, in_id = int(best["out_id"]), int(best["in_id"])
        state.bank += int(best["sale_price"]) - int(best["buy_price"])
        state.squad.pop(out_id)
        state.squad[in_id] = OwnedPlayer(in_id, int(best["buy_price"]))
        best["bank_after"] = state.bank
        moves.append(best)
    return moves


def _formation_ok(positions: list[str]) -> bool:
    counts = pd.Series(positions).value_counts().to_dict()
    return all(START_MIN[p] <= counts.get(p, 0) <= START_MAX[p] for p in START_MIN)


def actual_team_points(
    plan: pd.DataFrame,
    actual: pd.DataFrame,
    chip: str | None,
    hit_cost: int,
) -> tuple[int, list[int]]:
    """Apply captaincy, vice captaincy, autosubs, BB/TC and transfer hits."""
    truth = actual.set_index("id")
    rows = plan.set_index("id")
    captain = int(plan.loc[plan.role == "C", "id"].iloc[0])
    vice = int(plan.loc[plan.role == "VC", "id"].iloc[0])
    starters = plan[plan.role.isin(["C", "VC", "XI"])]
    starter_ids = starters.id.astype(int).tolist()
    bench_outfield = []
    for number in (1, 2, 3):
        hit = plan.loc[plan.role == f"Bench {number}", "id"]
        if len(hit):
            bench_outfield.append(int(hit.iloc[0]))
    bench_gk_row = plan.loc[plan.role == "GK bench", "id"]
    bench_gk = int(bench_gk_row.iloc[0]) if len(bench_gk_row) else None

    def minutes(player_id: int) -> int:
        return int(truth["minutes"].get(player_id, 0))

    def points(player_id: int) -> int:
        return int(truth["points"].get(player_id, 0))

    scoring = list(starter_ids)
    autosubs: list[int] = []
    if chip != "bench_boost":
        starting_gk = next(pid for pid in starter_ids if rows.loc[pid, "position"] == "GKP")
        if minutes(starting_gk) == 0 and bench_gk is not None and minutes(bench_gk) > 0:
            scoring.remove(starting_gk); scoring.append(bench_gk); autosubs.append(bench_gk)
        for missing in [pid for pid in list(scoring) if rows.loc[pid, "position"] != "GKP" and minutes(pid) == 0]:
            for replacement in bench_outfield:
                if replacement in scoring or minutes(replacement) == 0:
                    continue
                candidate = [pid for pid in scoring if pid != missing] + [replacement]
                positions = [str(rows.loc[pid, "position"]) for pid in candidate]
                if _formation_ok(positions):
                    scoring.remove(missing); scoring.append(replacement); autosubs.append(replacement)
                    break
    if chip == "bench_boost":
        scoring = plan.id.astype(int).tolist()

    score = sum(points(pid) for pid in scoring)
    active_captain = captain if minutes(captain) > 0 else (vice if minutes(vice) > 0 else None)
    if active_captain is not None:
        score += points(active_captain)
        if chip == "triple_captain":
            score += points(active_captain)
    return int(score - hit_cost), autosubs


def choose_chip(
    gw: int,
    state: ReplayState,
    opportunities: pd.DataFrame,
    cold_start_end: int = 5,
    late_cup_window_start: int = 28,
) -> str | None:
    """Choose a chip using only the rolling forecast available at this deadline.

    Each opportunity is an expected-points uplift versus not using that chip.
    The current GW must beat the same chip's other visible opportunities.  The
    second-half set is normally reserved for the late cup-driven BGW/DGW
    window, unless a confirmed special GW is already visible.  This is a
    strategic seasonal prior, not knowledge of future cup results.
    """
    half = 1 if gw <= 19 else 2
    end = 19 if half == 1 else 38
    available = [
        chip for chip in ("wildcard", "free_hit", "bench_boost", "triple_captain")
        if not any((used <= 19) == (half == 1) for used in state.chips_used[chip])
    ]
    if gw - 1 in state.chips_used["free_hit"] and "free_hit" in available:
        available.remove("free_hit")
    if not available:
        return None

    visible = opportunities[
        opportunities["gw"].between(gw, min(end, gw + 5))
    ].copy()
    current = visible[visible["gw"] == gw]
    if current.empty:
        return None

    thresholds = {"triple_captain": 8.0, "bench_boost": 10.0, "free_hit": 10.0, "wildcard": 12.0}
    remaining_weeks = end - gw + 1
    must_spend = remaining_weeks <= len(available)

    if not must_spend:
        if gw <= cold_start_end:
            return None
        if half == 2 and gw < late_cup_window_start:
            special = (
                visible.get("schedule_confirmed", pd.Series(False, index=visible.index)).fillna(False).astype(bool)
                & (
                    visible.get("blank_teams", pd.Series(0, index=visible.index)).fillna(0).ge(4)
                    | visible.get("double_teams", pd.Series(0, index=visible.index)).fillna(0).ge(2)
                )
            )
            if not bool(special.any()):
                return None

    values = {chip: float(current.iloc[0].get(chip, -999.0)) for chip in available}
    if must_spend:
        eligible = available
    else:
        eligible = []
        for chip in available:
            value = values[chip]
            future_best = float(pd.to_numeric(visible[chip], errors="coerce").max())
            if value >= thresholds[chip] and value >= future_best - 1e-9:
                eligible.append(chip)
    if not eligible:
        return None
    return max(eligible, key=lambda chip: values[chip] - thresholds[chip])


def initial_squad(origin: pd.DataFrame, meta: pd.DataFrame, gameweeks: list[int], budget: int = 1000) -> ReplayState:
    players = meta.copy()
    players["price"] = players["price_tenths"] / 10.0
    players["status"] = "a"
    result = optimize_squad_milp(origin, players, gameweeks, budget=budget / 10.0)
    if not result.get("success"):
        raise RuntimeError(f"Could not optimize initial squad: {result.get('message')}")
    ids = [int(x) for x in result["squad_ids"]]
    price = players.set_index("id")["price_tenths"].astype(int)
    spent = int(price.reindex(ids).sum())
    return ReplayState(
        squad={player_id: OwnedPlayer(player_id, int(price[player_id])) for player_id in ids},
        bank=budget - spent,
        # The initial squad is selected before GW1; the first normal free
        # transfer is credited only after that deadline has passed.
        free_transfers=0,
    )
