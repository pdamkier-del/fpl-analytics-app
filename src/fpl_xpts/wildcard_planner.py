from __future__ import annotations
"""Experimental permanent Wildcard action; locked TS modules remain unchanged."""
from dataclasses import dataclass
from typing import Any
import pandas as pd
from .optimize import optimize_squad_milp, plan_squad
from .season_replay import ReplayState, squad_sale_value, valid_squad
from .transfer_planner import _apply_selected_squad, clone_state, plan_transfer_path, PlannerConfig

@dataclass
class WildcardCandidate:
    state: ReplayState
    squad_ids: tuple[int, ...]
    budget_tenths: int
    changed: int
    weighted_score: float
    normal_objective: float
    wildcard_objective: float
    gain: float

def optimize_wildcard(state:ReplayState, meta:pd.DataFrame, origin:pd.DataFrame,
                      current_gw:int, config:PlannerConfig,
                      candidate_limit_per_position:int=35) -> WildcardCandidate:
    """Optimize a permanent 15-player squad then re-plan with locked TS.

    No chip activation policy is assumed. Uses only the deadline-origin forecast.
    Projected 6GW score is weighted with locked TS weights; after constructing
    a candidate, the locked TS planner evaluates both counterfactual states.
    """
    m=meta.drop_duplicates('id').copy()
    if 'status' not in m:m['status']='a'
    m['price']=m.price_tenths.astype(float)/10.
    horizon=[current_gw+i for i in range(len(config.weights)) if current_gw+i<=38]
    weight={gw:float(config.weights[i]) for i,gw in enumerate(horizon)}
    projections=origin[origin.gw.isin(horizon)].copy()
    projections['xpts_mean']=pd.to_numeric(projections.xpts_mean,errors='coerce').fillna(0.)*projections.gw.map(weight).fillna(0.)
    projections['gw']=int(current_gw)
    # Projection rows represent one weighted aggregate GW. Optimize one fixed
    # permanent squad, not a fictional independent squad per future GW.
    budget=int(state.bank+squad_sale_value(state,m))
    result=optimize_squad_milp(projections,m,[int(current_gw)],budget=budget/10.,
                              candidate_limit_per_position=candidate_limit_per_position)
    if not result.get('success'):
        raise RuntimeError('WC optimization failed: '+str(result.get('message')))
    ids=set(map(int,result['squad_ids']))
    if not valid_squad(m,ids):raise AssertionError('Illegal WC squad')
    after,outgoing,incoming=_apply_selected_squad(state,ids,m)
    if after.bank<0:raise AssertionError('WC negative bank')
    # Wildcard is permanent, all changes free, and existing FT balance persists.
    # (Chip-specific FT rules can be adjusted if official season rules differ.)
    after.free_transfers=int(state.free_transfers)
    after.chips_used['wildcard'].append(int(current_gw))
    normal=plan_transfer_path(clone_state(state),m,origin,int(current_gw),config)
    future=plan_transfer_path(clone_state(after),m,origin,int(current_gw),config)
    return WildcardCandidate(after,tuple(sorted(ids)),budget,len(incoming),
                             float(result.get('objective',0.)),
                             float(normal.objective),float(future.objective),
                             float(future.objective-normal.objective))
