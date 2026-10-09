from __future__ import annotations
"""Wildcard as an expanded, zero-hit FIRST ACTION of the locked TS v3.

The underlying locked TS remains unmodified. Wildcard candidate squads are
proposed using the SAME lineup-and-captain multi-GW MILP as TS with only the
per-week 0..5 transfer-count constraint removed. Every WC candidate is valued
using the original TS planner for FUTURE permanent moves.
"""
from dataclasses import dataclass
from dataclasses import replace
from typing import Any
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from .optimize import POSITION_COUNTS,START_MAX,START_MIN,plan_squad
from .season_replay import ReplayState,valid_squad,selling_price
from .transfer_planner import (
    PlannerConfig, PlannerResult, _candidate_players, _apply_selected_squad,
    clone_state,plan_transfer_path,execute_first_action,projected_manager_score,
)

@dataclass
class WCTransferComparison:
    state: ReplayState
    normal_result: PlannerResult
    chosen_squad: tuple[int,...]
    transfers: int
    wc_objective: float
    normal_objective: float
    gain: float
    candidates_tested: int

def _wc_milp_squads(
    state: ReplayState,
    meta: pd.DataFrame,
    origin: pd.DataFrame,
    gws: list[int],
    weights: list[float],
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



def compare_wc_as_ts_action(state:ReplayState,meta:pd.DataFrame,
                            origin:pd.DataFrame,gw:int,config:PlannerConfig,
                            max_candidates:int=3,milp_seconds:float=12.)->WCTransferComparison:
    """Compare normal TS versus zero-hit WC using identical 6GW inputs.

    The WC deadline counts as a decision GW; retained free transfers do NOT
    accrue at the end of this deadline. Following weeks use ordinary TS.
    """
    normal=plan_transfer_path(clone_state(state),meta,origin,gw,config)
    horizon=list(normal.horizon_gws)
    weights=list(normal.weights)
    if not horizon:raise RuntimeError('No TS horizon for WC comparison')
    selected=[set(state.squad)]
    # Include the normal TS first move: a WC can copy it without spending a FT
    # or taking a hit. This is also a candidate when the MILP misses it.
    if normal.first_action:
        replica,_,_=_apply_selected_squad(
            state, set(state.squad).difference(normal.first_action.outgoing)
            .union(normal.first_action.incoming),meta
        )
        selected.append(set(replica.squad))
    selected+=_wc_milp_squads(state,meta,origin,horizon,weights,max_candidates,
                              milp_seconds,config.candidate_limit_per_position)
    uniq=[];seen=set()
    for squad in selected:
        key=tuple(sorted(squad))
        if key not in seen:
            if not valid_squad(meta,key):raise AssertionError('WC candidate illegal')
            seen.add(key);uniq.append(squad)
    best=None
    for squad in uniq:
        after,outs,ins=_apply_selected_squad(state,set(squad),meta)
        assert after.bank>=0
        after.free_transfers=int(state.free_transfers)
        now=float(projected_manager_score(origin,meta,after.squad,gw))
        if len(horizon)>1:
            # Six original weights shift left as we start planning in GW+1.
            shift=replace(config,weights=tuple(weights[1:]))
            future=plan_transfer_path(after,meta,origin,gw+1,shift)
            objective=now+float(future.objective)
        else:
            objective=now
        if best is None or objective>best[0]:
            best=(objective,after,len(ins),tuple(sorted(squad)))
    if best is None:raise RuntimeError('WC failed to produce candidates')
    objective,after,transfer_count,ids=best
    after.chips_used['wildcard'].append(int(gw))
    return WCTransferComparison(after,normal,ids,int(transfer_count),
          float(objective),float(normal.objective),
          float(objective-normal.objective),len(uniq))
