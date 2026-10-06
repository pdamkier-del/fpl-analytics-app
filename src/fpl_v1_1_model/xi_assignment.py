"""Global XI role-slot assignment for the Minute Model.

This module converts player-level start evidence into a coherent most-likely XI.

Hard constraints
----------------
* exactly one player per formation slot;
* a player can occupy at most one slot;
* exactly 11 distinct starters;
* multi-role players may compete for every eligible role, but can only win one;
* eligibility is derived from cutoff-safe q(role) distributions;
* the optimizer never uses target-match realised lineup information.

The optimizer is deliberately separate from probabilistic P(start).  Its primary
output is the coherent MAP-style XI assignment used for explanation and for
role-competition features.  Player P(start) remains probabilistic for xMins.

A soft assignment/marginal layer can be added later, but must preserve the same
one-player/one-slot constraints.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import Iterable, Mapping, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

from .role_classifier import canonical, template

EPS=1e-9

@dataclass(frozen=True)
class Slot:
    index:int
    role:str

@dataclass(frozen=True)
class Assignment:
    player_uuid:str
    slot_index:int
    role:str
    score:float
    q_role:float
    hierarchy:float
    performance:float
    base_p_start:float
    role_adjustment:float=0.0


def formation_slots(formation:str)->list[Slot]:
    patterns=template(formation)
    if not patterns:
        raise ValueError(f"Unsupported formation: {formation}")
    roles=['GK']+[canonical(r) for layer in patterns for r in layer]
    if len(roles)!=11:
        raise AssertionError("Formation must produce exactly 11 slots")
    return [Slot(i,r) for i,r in enumerate(roles)]


def _safe01(x,default=0.0):
    try:
        z=float(x)
    except (TypeError,ValueError):
        return float(default)
    if not np.isfinite(z):
        return float(default)
    return min(1.0,max(0.0,z))


def role_score(*,q_role:float,hierarchy:float,performance:float,base_p_start:float,
               q_weight:float=1.0,h_weight:float=1.0,performance_weight:float=0.0,
               base_weight:float=1.0)->float:
    """Log-score for player i occupying role r.

    q_role controls role eligibility, H controls role-specific hierarchy,
    performance is a normalized recent form score in [0,1], and base_p_start is
    the already cutoff-safe player start probability before global assignment.

    The score is additive on log scale so evidence combines multiplicatively.
    """
    q=max(EPS,_safe01(q_role))
    h=max(EPS,_safe01(hierarchy))
    p=max(EPS,_safe01(base_p_start))
    f=max(EPS,_safe01(performance,0.5))
    return (q_weight*log(q)+h_weight*log(h)+
            performance_weight*log(f)+base_weight*log(p))


def build_score_matrix(players:Sequence[Mapping],slots:Sequence[Slot],*,
                       min_q:float=0.01,q_weight:float=1.0,h_weight:float=1.0,
                       performance_weight:float=0.0,base_weight:float=1.0,
                       impossible_penalty:float=-1e9)->np.ndarray:
    """Return players x slots score matrix.

    Each player mapping requires:
      player_uuid, base_p_start, q (dict), H (dict)
    and may contain performance in [0,1].
    """
    if len(players)<len(slots):
        raise ValueError("Need at least as many candidate players as slots")
    mat=np.full((len(players),len(slots)),float(impossible_penalty),dtype=float)
    for i,p in enumerate(players):
        q={canonical(k):_safe01(v) for k,v in dict(p.get('q') or {}).items()}
        h={canonical(k):_safe01(v) for k,v in dict(p.get('H') or {}).items()}
        base=_safe01(p.get('base_p_start'))
        perf=_safe01(p.get('performance',0.5),0.5)
        role_adjustments={canonical(k):float(v) for k,v in dict(p.get('role_adjustments') or {}).items()}
        for j,slot in enumerate(slots):
            qr=q.get(slot.role,0.0)
            hr=h.get(slot.role,0.0)
            if qr<min_q:
                continue
            mat[i,j]=role_score(q_role=qr,hierarchy=hr,performance=perf,
                                base_p_start=base,q_weight=q_weight,h_weight=h_weight,
                                performance_weight=performance_weight,base_weight=base_weight) + role_adjustments.get(slot.role,0.0)
    return mat


def optimize_xi(players:Sequence[Mapping],formation:str,**score_kwargs)->list[Assignment]:
    """Find the highest-scoring legal XI for one team/fixture."""
    slots=formation_slots(formation)
    mat=build_score_matrix(players,slots,**score_kwargs)
    rows,cols=linear_sum_assignment(-mat)
    if len(cols)!=11:
        raise RuntimeError("Could not assign all 11 slots")
    chosen=sorted(zip(rows,cols),key=lambda z:z[1])
    out=[]
    for i,j in chosen:
        if mat[i,j] < -1e8:
            raise RuntimeError(f"No eligible candidate for slot {slots[j].role}")
        p=players[i];role=slots[j].role
        q={canonical(k):_safe01(v) for k,v in dict(p.get('q') or {}).items()}
        h={canonical(k):_safe01(v) for k,v in dict(p.get('H') or {}).items()}
        out.append(Assignment(
            player_uuid=str(p['player_uuid']),slot_index=slots[j].index,role=role,
            score=float(mat[i,j]),q_role=q.get(role,0.0),hierarchy=h.get(role,0.0),
            performance=_safe01(p.get('performance',0.5),0.5),
            base_p_start=_safe01(p.get('base_p_start')),
            role_adjustment=float(dict(p.get('role_adjustments') or {}).get(role,0.0)),
        ))
    ids=[x.player_uuid for x in out]
    if len(ids)!=11 or len(set(ids))!=11:
        raise AssertionError("XI assignment must contain 11 unique players")
    return out


def assignment_explanations(assignments:Iterable[Assignment])->list[dict]:
    return [{
        'player_uuid':a.player_uuid,'slot_index':a.slot_index,'role':a.role,
        'assignment_score':a.score,'q_role':a.q_role,'hierarchy':a.hierarchy,
        'performance':a.performance,'base_p_start':a.base_p_start,
        'role_adjustment':a.role_adjustment
    } for a in assignments]


DEFAULT_FORMATIONS=('4-2-3-1','4-3-3','4-4-2','3-4-2-1','3-4-3','3-5-2')


def optimize_best_formation(players:Sequence[Mapping],
                            formations:Sequence[str]=DEFAULT_FORMATIONS,
                            formation_log_prior:Mapping[str,float]|None=None,
                            **score_kwargs):
    """Return the highest-scoring legal formation + XI.

    formation_log_prior is optional cutoff-safe historical formation evidence.
    It is additive in log-space.  Unsupported/infeasible formations are skipped.
    """
    priors=dict(formation_log_prior or {})
    candidates=[]
    for formation in formations:
        try:
            xi=optimize_xi(players,formation,**score_kwargs)
        except (ValueError,RuntimeError):
            continue
        score=sum(a.score for a in xi)+float(priors.get(formation,0.0))
        candidates.append((score,formation,xi))
    if not candidates:
        raise RuntimeError("No feasible formation/XI assignment")
    candidates.sort(key=lambda x:(x[0],x[1]),reverse=True)
    score,formation,xi=candidates[0]
    return {
        'formation':formation,
        'score':float(score),
        'xi':xi,
        'alternatives':[{'formation':f,'score':float(s)} for s,f,_ in candidates],
    }
