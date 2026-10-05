from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp

from .optimize import POSITION_COUNTS, START_MAX, START_MIN, plan_squad
from .season_replay import OwnedPlayer, ReplayState, selling_price, valid_squad


@dataclass(frozen=True)
class PlannerConfig:
    """Configuration for the chip-free rolling transfer planner."""

    weights: tuple[float, ...] = (1.00, 0.85, 0.70, 0.55, 0.40, 0.25)
    hit_uncertainty_buffer: float = 1.5
    beam_width: int = 30
    candidates_per_transfer_count: int = 2
    candidate_limit_per_position: int = 18
    top_targets_per_position: int = 18
    local_bundle_beam: int = 60
    candidate_return_per_depth: int = 12
    max_transfers_per_week: int = 5
    candidate_backend: str = "fast_local"
    discount_transfer_costs: bool = True
    milp_time_limit: float = 12.0


@dataclass
class TransferAction:
    gw: int
    outgoing: tuple[int, ...]
    incoming: tuple[int, ...]
    transfers: int
    official_hit_points: int
    uncertainty_penalty: float
    projected_manager_score: float
    utility_this_gw: float
    free_transfers_before: int
    free_transfers_after: int
    bank_before: int
    bank_after: int


@dataclass
class PlannerNode:
    state: ReplayState
    objective: float
    path: list[TransferAction] = field(default_factory=list)
    rank_score: float = 0.0


@dataclass
class PlannerResult:
    current_gw: int
    horizon_gws: tuple[int, ...]
    weights: tuple[float, ...]
    objective: float
    path: list[TransferAction]

    @property
    def first_action(self) -> TransferAction | None:
        return self.path[0] if self.path else None


def clone_state(state: ReplayState) -> ReplayState:
    return ReplayState(
        squad={
            int(pid): OwnedPlayer(int(pid), int(owned.purchase_price))
            for pid, owned in state.squad.items()
        },
        bank=int(state.bank),
        free_transfers=int(state.free_transfers),
        chips_used={key: list(values) for key, values in state.chips_used.items()},
    )


def next_free_transfers(free_transfers: int, transfers_made: int) -> int:
    """FPL FT transition after a deadline, capped at five."""
    return min(5, max(0, int(free_transfers) - int(transfers_made)) + 1)


def transfer_penalties(
    free_transfers: int,
    transfers_made: int,
    hit_uncertainty_buffer: float,
) -> tuple[int, float]:
    """Return official hit points and extra forecast-risk penalty.

    Free transfers carry no artificial option-value charge. Their future value
    is represented by the next state's FT count.
    """
    hits = max(0, int(transfers_made) - int(free_transfers))
    return 4 * hits, float(hit_uncertainty_buffer) * hits


def _state_key(state: ReplayState) -> tuple:
    purchases = tuple(sorted((int(pid), int(x.purchase_price)) for pid, x in state.squad.items()))
    return purchases, int(state.bank), int(state.free_transfers)


def _projection_for_squad(
    origin: pd.DataFrame,
    meta: pd.DataFrame,
    squad_ids: Iterable[int],
    gw: int,
) -> pd.DataFrame:
    ids = [int(x) for x in squad_ids]
    base = meta[meta.id.isin(ids)][["id", "web_name", "team", "position"]].drop_duplicates("id").copy()
    cols = ["id", "xpts_mean"] + (["p_play"] if "p_play" in origin.columns else [])
    forecast = origin[origin.gw.eq(gw)][cols].copy()
    agg = {"xpts_mean": "sum"}
    if "p_play" in forecast.columns:
        agg["p_play"] = "max"
    forecast = forecast.groupby("id", as_index=False).agg(agg)
    frame = base.merge(forecast, on="id", how="left")
    frame["gw"] = int(gw)
    frame["xpts_mean"] = frame["xpts_mean"].fillna(0.0).astype(float)
    if "p_play" not in frame.columns:
        frame["p_play"] = 1.0
    else:
        frame["p_play"] = frame["p_play"].fillna(1.0).clip(0.0, 1.0)
    if len(frame) != 15:
        missing = sorted(set(ids) - set(frame.id.astype(int)))
        raise RuntimeError(f"GW{gw}: planner missing squad metadata for {missing}")
    return frame


def projected_manager_score(
    origin: pd.DataFrame,
    meta: pd.DataFrame,
    squad_ids: Iterable[int],
    gw: int,
) -> float:
    ids = list(map(int, squad_ids))
    projection = _projection_for_squad(origin, meta, ids, gw)
    return float(plan_squad(projection, ids, int(gw)).expected_score)


def _candidate_players(
    state: ReplayState,
    meta: pd.DataFrame,
    origin: pd.DataFrame,
    gws: list[int],
    weights: list[float],
    candidate_limit_per_position: int,
) -> pd.DataFrame:
    owned = set(map(int, state.squad))
    frame = origin[origin.gw.isin(gws)].copy()
    weight_by_gw = {int(gw): float(w) for gw, w in zip(gws, weights)}
    frame["weighted_xpts"] = [
        float(x) * weight_by_gw.get(int(gw), 0.0)
        for x, gw in zip(frame.xpts_mean, frame.gw)
    ]
    values = frame.groupby("id")["weighted_xpts"].sum()
    pool = set(owned)
    meta_unique = meta.drop_duplicates("id")
    for position in POSITION_COUNTS:
        ids = meta_unique[meta_unique.position.eq(position)].id.astype(int)
        ranked = values.reindex(ids).fillna(0.0).nlargest(int(candidate_limit_per_position))
        pool.update(int(x) for x in ranked.index)
    players = meta_unique[meta_unique.id.isin(pool)].copy().reset_index(drop=True)
    if not owned.issubset(set(players.id.astype(int))):
        missing = sorted(owned - set(players.id.astype(int)))
        raise RuntimeError(f"planner missing owned players: {missing}")

    pivot = origin[origin.gw.isin(gws)].pivot_table(
        index="id", columns="gw", values="xpts_mean", aggfunc="sum", fill_value=0.0
    )
    for gw in gws:
        players[f"xpts_{gw}"] = players.id.map(
            pivot[gw] if gw in pivot.columns else pd.Series(dtype=float)
        ).fillna(0.0).astype(float)

    prices = players.set_index("id").price_tenths.astype(int).to_dict()
    sale_prices = {
        pid: selling_price(owned_player.purchase_price, int(prices[pid]))
        for pid, owned_player in state.squad.items()
    }
    players["owned"] = players.id.isin(owned)
    players["effective_price"] = [
        sale_prices[int(row.id)] if bool(row.owned) else int(row.price_tenths)
        for row in players.itertuples()
    ]
    return players



def _weighted_player_values(
    origin: pd.DataFrame,
    gws: list[int],
    weights: list[float],
) -> pd.Series:
    frame = origin[origin.gw.isin(gws)][["id", "gw", "xpts_mean"]].copy()
    weight_by_gw = {int(gw): float(w) for gw, w in zip(gws, weights)}
    frame["weighted"] = [
        float(x) * weight_by_gw.get(int(gw), 0.0)
        for x, gw in zip(frame.xpts_mean, frame.gw)
    ]
    return frame.groupby("id")["weighted"].sum()


def _prepare_local_candidates(meta, origin, gws, weights, top_targets):
    """Immutable deadline inputs shared by all nodes at the same path depth."""
    by_id = meta.drop_duplicates("id").set_index("id")
    values = _weighted_player_values(origin, gws, weights)
    targets = {}
    for position in POSITION_COUNTS:
        ids = by_id[by_id.position.eq(position)].index.astype(int)
        ranked = values.reindex(ids).fillna(0.0).sort_values(ascending=False)
        targets[position] = [int(x) for x in ranked.head(int(top_targets)).index]
    rows = {int(pid): (str(r.position), r.team, int(r.price_tenths))
            for pid, r in by_id.iterrows()}
    return rows, values.to_dict(), targets


def _fast_local_candidate_squads(
    state: ReplayState,
    meta: pd.DataFrame,
    origin: pd.DataFrame,
    gws: list[int],
    weights: list[float],
    max_transfers: int,
    top_targets_per_position: int,
    local_bundle_beam: int,
    candidate_return_per_depth: int,
    prepared: tuple | None = None,
) -> list[set[int]]:
    """Generate strong legal transfer bundles without solving a MILP.

    This is the performance-oriented candidate generator for the rolling
    planner.  It searches bundles locally, keeps exact bank/sale-price/team
    constraints, and ranks partial bundles by weighted player-value gain.
    Final path evaluation is still lineup-aware (XI + captain) in the outer
    planner, so this heuristic is only used to propose plausible squads.
    """
    if prepared is None:
        prepared = _prepare_local_candidates(meta, origin, gws, weights, top_targets_per_position)
    rows, values, target_pool = prepared
    owned0 = set(map(int, state.squad))

    # tuple: (rank_gain, squad_set, bank, purchase_prices, moves)
    purchase0 = {int(pid): int(op.purchase_price) for pid, op in state.squad.items()}
    frontier = [(0.0, owned0, int(state.bank), purchase0, 0)]
    out: list[set[int]] = [set(owned0)]

    for depth in range(1, max(0, int(max_transfers)) + 1):
        next_frontier = []
        seen = {}
        for rank_gain, squad, bank, purchases, _moves in frontier:
            team_counts = {}
            for pid in squad:
                team = rows[pid][1]
                team_counts[team] = team_counts.get(team, 0) + 1
            # Prefer replacing low weighted-value players first.
            outs = sorted(
                squad,
                key=lambda pid: float(values.get(int(pid), 0.0))
            )
            for out_id in outs:
                position, out_team, current_price = rows[out_id]
                sale = selling_price(int(purchases[out_id]), current_price)
                for in_id in target_pool.get(position, []):
                    if in_id in squad:
                        continue
                    _, in_team, buy = rows[in_id]
                    if buy > sale + bank:
                        continue
                    if in_team != out_team and team_counts.get(in_team, 0) >= 3:
                        continue

                    new_squad = set(squad)
                    new_squad.remove(int(out_id))
                    new_squad.add(int(in_id))
                    # Prevent immediate buy-back loops inside the same bundle by
                    # requiring each depth to increase weighted player value.
                    gain = float(values.get(in_id, 0.0) - values.get(out_id, 0.0))
                    if gain <= -1e-12:
                        continue
                    new_bank = int(bank + sale - buy)
                    new_purchases = dict(purchases)
                    new_purchases.pop(int(out_id))
                    new_purchases[int(in_id)] = buy
                    new_gain = float(rank_gain + gain)
                    key = tuple(sorted(new_squad))
                    prev = seen.get(key)
                    item = (new_gain, new_squad, new_bank, new_purchases, depth)
                    if prev is None or new_gain > prev[0] + 1e-12:
                        seen[key] = item

        next_frontier = sorted(
            seen.values(),
            key=lambda x: (x[0], x[2]),
            reverse=True,
        )[:max(1, int(local_bundle_beam))]
        frontier = next_frontier
        # Keep the internal search broad, but only return the strongest few
        # candidates from each exact transfer-count depth to the expensive
        # outer path scorer. Every depth 1..max_transfers remains represented.
        out.extend(set(item[1]) for item in frontier[:max(1, int(candidate_return_per_depth))])
        if not frontier:
            break

    # De-duplicate while preserving search order.
    unique = []
    seen_keys = set()
    for squad in out:
        key = tuple(sorted(squad))
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(set(squad))
    return unique


def _top_squads_for_transfer_count(
    state: ReplayState,
    meta: pd.DataFrame,
    origin: pd.DataFrame,
    gws: list[int],
    weights: list[float],
    transfer_count: int,
    top_k: int,
    time_limit: float,
    candidate_limit_per_position: int,
) -> list[set[int]]:
    """Generate strong immediate squads for a given transfer count.

    Candidate generation assumes the post-transfer squad is held over the
    remaining visible horizon and optimizes XI plus captain each GW. The beam
    search can then make further transfers in later hypothetical GWs.
    """
    players = _candidate_players(
        state, meta, origin, gws, weights, candidate_limit_per_position
    )
    n = len(players)
    h = len(gws)
    if transfer_count < 0 or transfer_count > 5:
        return []

    owned = set(map(int, state.squad))
    prices = players.set_index("id").price_tenths.astype(int).to_dict()
    sale_prices = {
        pid: selling_price(state.squad[pid].purchase_price, int(prices[pid]))
        for pid in owned
    }
    resources = int(state.bank + sum(sale_prices.values()))

    total_vars = n + 2 * h * n
    objective = np.zeros(total_vars)
    for gi, (gw, weight) in enumerate(zip(gws, weights)):
        xp = players[f"xpts_{gw}"].to_numpy(float)
        s0 = n + gi * n
        c0 = n + h * n + gi * n
        objective[s0:s0 + n] = -float(weight) * xp
        objective[c0:c0 + n] = -float(weight) * xp

    base_rows: list[np.ndarray] = []
    lower: list[float] = []
    upper: list[float] = []

    def blank() -> np.ndarray:
        return np.zeros(total_vars)

    for position, count in POSITION_COUNTS.items():
        row = blank(); row[:n] = (players.position == position).to_numpy(float)
        base_rows.append(row); lower.append(float(count)); upper.append(float(count))
    for team in players.team.dropna().unique():
        row = blank(); row[:n] = (players.team == team).to_numpy(float)
        base_rows.append(row); lower.append(-np.inf); upper.append(3.0)
    row = blank(); row[:n] = players.effective_price.to_numpy(float)
    base_rows.append(row); lower.append(-np.inf); upper.append(float(resources))
    row = blank(); row[:n] = (~players.owned).to_numpy(float)
    base_rows.append(row); lower.append(float(transfer_count)); upper.append(float(transfer_count))

    for gi, _gw in enumerate(gws):
        s0 = n + gi * n
        c0 = n + h * n + gi * n
        row = blank(); row[s0:s0 + n] = 1.0
        base_rows.append(row); lower.append(11.0); upper.append(11.0)
        row = blank(); row[c0:c0 + n] = 1.0
        base_rows.append(row); lower.append(1.0); upper.append(1.0)

        for position in START_MIN:
            mask = (players.position == position).to_numpy(float)
            row = blank(); row[s0:s0 + n] = mask
            base_rows.append(row); lower.append(float(START_MIN[position])); upper.append(float(START_MAX[position]))

        for i in range(n):
            row = blank(); row[s0 + i] = 1.0; row[i] = -1.0
            base_rows.append(row); lower.append(-np.inf); upper.append(0.0)
            row = blank(); row[c0 + i] = 1.0; row[s0 + i] = -1.0
            base_rows.append(row); lower.append(-np.inf); upper.append(0.0)

    exclusions: list[np.ndarray] = []
    results: list[set[int]] = []
    for _ in range(max(1, int(top_k))):
        rows = base_rows + exclusions
        lo = lower + [-np.inf] * len(exclusions)
        hi = upper + [14.0] * len(exclusions)
        result = milp(
            c=objective,
            integrality=np.ones(total_vars),
            bounds=Bounds(0.0, 1.0),
            constraints=LinearConstraint(np.vstack(rows), np.asarray(lo), np.asarray(hi)),
            options={"time_limit": float(time_limit)},
        )
        if result.x is None:
            break
        selected = set(players.loc[result.x[:n] > 0.5, "id"].astype(int))
        if len(selected) != 15:
            break
        results.append(selected)
        exclusion = blank()
        selected_indices = [int(players.index[players.id.eq(pid)][0]) for pid in selected]
        exclusion[selected_indices] = 1.0
        exclusions.append(exclusion)
    return results


def _apply_selected_squad(
    state: ReplayState,
    selected: set[int],
    meta: pd.DataFrame,
    prices: dict[int, int] | None = None,
) -> tuple[ReplayState, tuple[int, ...], tuple[int, ...]]:
    next_state = clone_state(state)
    owned = set(map(int, state.squad))
    outgoing = tuple(sorted(owned - selected))
    incoming = tuple(sorted(selected - owned))
    if len(outgoing) != len(incoming):
        raise RuntimeError("planner transfer bundle is not balanced")

    if prices is None:
        prices = meta.drop_duplicates("id").set_index("id").price_tenths.astype(int).to_dict()
    sale_value = sum(
        selling_price(state.squad[pid].purchase_price, prices[pid])
        for pid in outgoing
    )
    buy_cost = sum(prices[pid] for pid in incoming)
    next_state.bank = int(state.bank + sale_value - buy_cost)
    if next_state.bank < 0:
        raise RuntimeError("planner produced unaffordable transfer bundle")

    for pid in outgoing:
        next_state.squad.pop(pid)
    for pid in incoming:
        next_state.squad[pid] = OwnedPlayer(pid, prices[pid])
    return next_state, outgoing, incoming


def _build_fast_score_context(origin: pd.DataFrame, meta: pd.DataFrame, gws: list[int]) -> dict:
    """Precompute exact inputs needed for repeated XI/captain scoring."""
    meta_unique = meta.drop_duplicates("id").set_index("id")
    ctx = {}
    for gw in gws:
        f = origin[origin.gw.eq(gw)][["id", "xpts_mean"] + (["p_play"] if "p_play" in origin.columns else [])].copy()
        agg = {"xpts_mean": "sum"}
        if "p_play" in f.columns:
            agg["p_play"] = "max"
        f = f.groupby("id", as_index=False).agg(agg).set_index("id")
        xp = f["xpts_mean"].to_dict()
        pp = f["p_play"].to_dict() if "p_play" in f.columns else {}
        ctx[int(gw)] = {
            "xp": {int(k): float(v) for k, v in xp.items()},
            "p_play": {int(k): float(v) for k, v in pp.items()},
            "position": {int(pid): str(meta_unique.loc[pid, "position"]) for pid in meta_unique.index},
        }
    return ctx


def _fast_manager_score(ctx: dict, squad_ids: Iterable[int], gw: int) -> float:
    """Exact equivalent of plan_squad.expected_score for repeated search scoring."""
    data = ctx[int(gw)]
    xp = data["xp"]; pp = data["p_play"]; pos = data["position"]
    squad = [int(x) for x in squad_ids]

    by_pos = {p: [] for p in POSITION_COUNTS}
    for pid in squad:
        by_pos[pos[pid]].append(pid)
    for p in by_pos:
        by_pos[p].sort(key=lambda pid: xp.get(pid, 0.0), reverse=True)

    if len(by_pos["GKP"]) < 2:
        return -1e9
    gk = by_pos["GKP"][0]

    best_ids = None
    best_xi = -1e18
    for defenders in range(3, 6):
        for midfielders in range(2, 6):
            forwards = 10 - defenders - midfielders
            if forwards < 1 or forwards > 3:
                continue
            if len(by_pos["DEF"]) < defenders or len(by_pos["MID"]) < midfielders or len(by_pos["FWD"]) < forwards:
                continue
            ids = [gk] + by_pos["DEF"][:defenders] + by_pos["MID"][:midfielders] + by_pos["FWD"][:forwards]
            value = sum(xp.get(pid, 0.0) for pid in ids)
            if value > best_xi:
                best_xi = float(value)
                best_ids = ids
    if best_ids is None:
        return -1e9

    # Match optimize._captain_pair exactly.
    best_cap = -1e18
    for captain in best_ids:
        c_xp = xp.get(captain, 0.0)
        c_pp = min(1.0, max(0.0, pp.get(captain, 1.0)))
        for vice in best_ids:
            if vice == captain:
                continue
            val = c_xp + (1.0 - c_pp) * xp.get(vice, 0.0)
            if val > best_cap:
                best_cap = float(val)
    return float(best_xi + best_cap)


def _hold_heuristic(
    state: ReplayState,
    origin: pd.DataFrame,
    meta: pd.DataFrame,
    future_gws: list[int],
    future_weights: list[float],
) -> float:
    return float(sum(
        float(weight) * projected_manager_score(origin, meta, state.squad, gw)
        for gw, weight in zip(future_gws, future_weights)
    ))


def plan_transfer_path(
    state: ReplayState,
    meta: pd.DataFrame,
    origin: pd.DataFrame,
    current_gw: int,
    config: PlannerConfig = PlannerConfig(),
) -> PlannerResult:
    """Plan a dynamic path over the visible horizon.

    Prices are frozen at the current deadline snapshot inside the hypothetical
    path, so future price changes cannot leak into the decision. Free-transfer
    value is endogenous through state transitions. Only the first action should
    be executed; the planner should be run again at the next deadline.
    """
    if not valid_squad(meta, state.squad):
        raise ValueError("planner requires a valid 15-player starting squad")

    available = set(int(gw) for gw in origin.gw.unique())
    horizon_gws = [
        gw for gw in range(int(current_gw), int(current_gw) + len(config.weights))
        if gw in available
    ]
    if not horizon_gws:
        return PlannerResult(int(current_gw), (), (), 0.0, [])

    weights = list(config.weights[:len(horizon_gws)])
    score_ctx = _build_fast_score_context(origin, meta, horizon_gws)
    score_cache: dict[tuple[int, tuple[int, ...]], float] = {}

    def score_for(squad_ids: Iterable[int], gw: int) -> float:
        key = (int(gw), tuple(sorted(int(x) for x in squad_ids)))
        if key not in score_cache:
            score_cache[key] = _fast_manager_score(score_ctx, key[1], int(gw))
        return score_cache[key]

    prices = meta.drop_duplicates("id").set_index("id").price_tenths.astype(int).to_dict()
    beam = [PlannerNode(clone_state(state), 0.0, [], 0.0)]

    for depth, gw in enumerate(horizon_gws):
        weight = float(weights[depth])
        expanded: list[PlannerNode] = []
        prepared = _prepare_local_candidates(
            meta, origin, horizon_gws[depth:], weights[depth:], config.top_targets_per_position
        ) if config.candidate_backend == "fast_local" else None
        candidate_cache = {}

        for node in beam:
            ft_before = int(node.state.free_transfers)
            candidate_squads: list[set[int]] = [set(map(int, node.state.squad))]
            remaining_gws = horizon_gws[depth:]
            remaining_weights = weights[depth:]

            max_count = min(int(config.max_transfers_per_week), 5)
            # Search the full legal 0-5 transfer range. The uncertainty buffer
            # and official hit cost decide whether deep hit paths survive;
            # there is no hard FT+1 pruning.
            search_count = max_count
            if str(config.candidate_backend) == "fast_local":
                # FT changes penalties, not the feasible bundles. Reuse generation
                # for identical squad, purchase prices and bank at this depth.
                candidate_key = _state_key(node.state)[:2]
                if candidate_key not in candidate_cache:
                    candidate_cache[candidate_key] = _fast_local_candidate_squads(
                        node.state, meta, origin, remaining_gws, remaining_weights,
                        search_count, int(config.top_targets_per_position),
                        int(config.local_bundle_beam),
                        int(config.candidate_return_per_depth), prepared,
                    )
                candidate_squads.extend(candidate_cache[candidate_key])
            else:
                candidate_counts = sorted({
                    1,
                    min(max_count, max(1, ft_before)),
                    min(max_count, max(1, ft_before + 1)),
                })
                for transfer_count in candidate_counts:
                    candidate_squads.extend(_top_squads_for_transfer_count(
                        node.state, meta, origin, remaining_gws, remaining_weights,
                        transfer_count, int(config.candidates_per_transfer_count),
                        float(config.milp_time_limit),
                        int(config.candidate_limit_per_position),
                    ))

            seen_squads: set[tuple[int, ...]] = set()
            for selected in candidate_squads:
                squad_key = tuple(sorted(selected))
                if squad_key in seen_squads:
                    continue
                seen_squads.add(squad_key)

                after, outgoing, incoming = _apply_selected_squad(node.state, selected, meta, prices)
                transfers = len(incoming)
                official_hit, uncertainty = transfer_penalties(
                    ft_before, transfers, config.hit_uncertainty_buffer
                )
                score = score_for(after.squad, gw)
                utility = float(score - official_hit - uncertainty)
                after.free_transfers = next_free_transfers(ft_before, transfers)

                action = TransferAction(
                    gw=int(gw),
                    outgoing=outgoing,
                    incoming=incoming,
                    transfers=int(transfers),
                    official_hit_points=int(official_hit),
                    uncertainty_penalty=float(uncertainty),
                    projected_manager_score=float(score),
                    utility_this_gw=utility,
                    free_transfers_before=ft_before,
                    free_transfers_after=int(after.free_transfers),
                    bank_before=int(node.state.bank),
                    bank_after=int(after.bank),
                )
                if config.discount_transfer_costs:
                    objective_increment = weight * utility
                else:
                    # Diagnostic alternative: forecast points decay with horizon,
                    # but deterministic FPL hit/buffer costs do not.
                    objective_increment = weight * score - official_hit - uncertainty
                objective = float(node.objective + objective_increment)

                future_gws = horizon_gws[depth + 1:]
                future_weights = weights[depth + 1:]
                heuristic = float(sum(
                    float(w) * score_for(after.squad, fg)
                    for fg, w in zip(future_gws, future_weights)
                )) if future_gws else 0.0
                expanded.append(PlannerNode(
                    state=after,
                    objective=objective,
                    path=node.path + [action],
                    rank_score=objective + heuristic,
                ))

        best_by_state: dict[tuple, PlannerNode] = {}
        for node in expanded:
            key = _state_key(node.state)
            current = best_by_state.get(key)
            if current is None or node.rank_score > current.rank_score + 1e-12:
                best_by_state[key] = node

        beam = sorted(
            best_by_state.values(),
            key=lambda node: (node.rank_score, node.objective),
            reverse=True,
        )[:max(1, int(config.beam_width))]
        if not beam:
            break

    if not beam:
        return PlannerResult(int(current_gw), tuple(horizon_gws), tuple(weights), 0.0, [])

    best = max(beam, key=lambda node: node.objective)
    return PlannerResult(
        current_gw=int(current_gw),
        horizon_gws=tuple(horizon_gws),
        weights=tuple(weights),
        objective=float(best.objective),
        path=best.path,
    )


def execute_first_action(
    state: ReplayState,
    result: PlannerResult,
    meta: pd.DataFrame,
) -> list[dict]:
    """Apply only the current-GW action and return replay-friendly rows."""
    action = result.first_action
    if action is None:
        return []

    selected = (set(state.squad) - set(action.outgoing)) | set(action.incoming)
    after, outgoing, incoming = _apply_selected_squad(state, selected, meta)
    state.squad = after.squad
    state.bank = after.bank
    state.free_transfers = int(action.free_transfers_after)

    by_id = meta.drop_duplicates("id").set_index("id")
    rows = []
    for position in POSITION_COUNTS:
        outs = [pid for pid in outgoing if str(by_id.loc[pid, "position"]) == position]
        ins = [pid for pid in incoming if str(by_id.loc[pid, "position"]) == position]
        for out_id, in_id in zip(sorted(outs), sorted(ins)):
            rows.append({
                "out_id": int(out_id),
                "in_id": int(in_id),
                "out": str(by_id.loc[out_id, "web_name"]),
                "in": str(by_id.loc[in_id, "web_name"]),
                "hit": 0,
                "decision_buffer": float(action.uncertainty_penalty),
                "bank_after": int(state.bank),
                "planner": "rolling_6gw_v3",
            })

    remaining = int(action.official_hit_points)
    for row in reversed(rows):
        if remaining <= 0:
            break
        row["hit"] = 4
        remaining -= 4
    return rows
