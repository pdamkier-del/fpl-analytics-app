from __future__ import annotations

"""Free-Hit-aware rolling TS planner.

The base transfer planner remains chip-free unless PlannerConfig.free_hit_gw
is explicitly set. This module evaluates alternative paths with one temporary
FH bridge and compares their total visible-horizon utility with the untouched
no-chip path.
"""

from dataclasses import dataclass, replace

import pandas as pd

from .chip_planner import optimize_free_hit_squad
from .season_replay import ReplayState
from .transfer_planner import (
    PlannerConfig, PlannerResult, _apply_selected_squad, clone_state,
    plan_transfer_path,
)


@dataclass
class FHBridgeEvaluation:
    gw: int
    planner_result: PlannerResult
    fh_score: float
    combined_objective: float
    uplift_vs_no_fh: float
    fh_plan: dict


@dataclass
class FHAwarePlannerResult:
    normal_result: PlannerResult
    active_result: PlannerResult
    recommended_fh_gw: int | None
    use_fh_now: bool
    normal_objective: float
    active_objective: float
    bridge_candidates: list[FHBridgeEvaluation]


def _state_before_target(
    state: ReplayState,
    result: PlannerResult,
    meta: pd.DataFrame,
    target_gw: int,
) -> ReplayState:
    s=clone_state(state)
    for action in result.path:
        if int(action.gw) >= int(target_gw):
            break
        selected=(set(s.squad)-set(action.outgoing))|set(action.incoming)
        nxt,_,_=_apply_selected_squad(s,selected,meta)
        s.squad=nxt.squad
        s.bank=nxt.bank
        s.free_transfers=int(action.free_transfers_after)
    return s


def evaluate_fh_aware_path(
    state: ReplayState,
    meta: pd.DataFrame,
    origin: pd.DataFrame,
    current_gw: int,
    *,
    period_end_gw: int,
    min_fh_gw: int,
    config: PlannerConfig,
    allow_fh: bool = True,
) -> FHAwarePlannerResult:
    """Compare the ordinary TS path with every visible one-GW FH bridge.

    If a future FH path is best, its *first permanent transfer action* becomes
    the active TS action now. That is the key bridge behaviour: TS may buy for
    post-FH fixtures even when the player is poor in the FH gameweek itself.

    The chip is executed only when recommended_fh_gw == current_gw.
    """
    base_cfg=replace(config,free_hit_gw=None)
    normal=plan_transfer_path(state,meta,origin,current_gw,base_cfg)
    if not allow_fh or not normal.horizon_gws:
        return FHAwarePlannerResult(normal,normal,None,False,float(normal.objective),float(normal.objective),[])

    visible=[int(g) for g in normal.horizon_gws
             if int(g)>=int(min_fh_gw) and int(g)<=int(period_end_gw)]
    if int(current_gw)==int(period_end_gw):
        visible=[int(current_gw)] if int(current_gw) in normal.horizon_gws else []

    candidates=[]
    original_weight_by_gw={int(g):float(w) for g,w in zip(normal.horizon_gws,config.weights)}
    for fh_gw in visible:
        bridge=plan_transfer_path(
            state,meta,origin,current_gw,replace(config,free_hit_gw=int(fh_gw))
        )
        bridge_state=_state_before_target(state,bridge,meta,fh_gw)
        fh=optimize_free_hit_squad(
            state=bridge_state,meta=meta,forecast=origin,gw=int(fh_gw),normal_score=0.0
        )
        w=float(original_weight_by_gw[int(fh_gw)])
        combined=float(bridge.objective+w*float(fh['fh_score']))
        candidates.append(FHBridgeEvaluation(
            gw=int(fh_gw),planner_result=bridge,fh_score=float(fh['fh_score']),
            combined_objective=combined,uplift_vs_no_fh=float(combined-normal.objective),
            fh_plan=fh,
        ))

    if not candidates:
        return FHAwarePlannerResult(normal,normal,None,False,float(normal.objective),float(normal.objective),[])

    best=max(candidates,key=lambda x:x.combined_objective)
    forced=int(current_gw)==int(period_end_gw)
    if forced or best.combined_objective>float(normal.objective)+1e-12:
        return FHAwarePlannerResult(
            normal_result=normal,active_result=best.planner_result,
            recommended_fh_gw=int(best.gw),use_fh_now=int(best.gw)==int(current_gw),
            normal_objective=float(normal.objective),active_objective=float(best.combined_objective),
            bridge_candidates=candidates,
        )
    return FHAwarePlannerResult(
        normal_result=normal,active_result=normal,recommended_fh_gw=None,use_fh_now=False,
        normal_objective=float(normal.objective),active_objective=float(normal.objective),
        bridge_candidates=candidates,
    )
