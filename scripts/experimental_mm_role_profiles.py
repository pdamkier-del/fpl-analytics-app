"""Research-only per-player MM role profile with separate starts and duration.

Roles are *descriptive soft labels*, not causal classes. Never uses target data.
Unknown/unavailable starts do not count as tactical bench evidence.
"""
from __future__ import annotations
import math
from datetime import datetime

def _weights(events, cutoff, half_life_days):
    if not math.isfinite(float(half_life_days)) or half_life_days <= 0: raise ValueError("half-life must be positive and finite")
    out=[]
    seen=set()
    for e in events:
        t=e["known_at"]
        if t>=cutoff: continue
        if e.get("available") is not True: continue
        key=e.get('fixture_uuid',t)
        if key in seen: raise ValueError('Duplicate role observation')
        seen.add(key)
        if e.get("started") not in (True,False): raise ValueError("Invalid start label")
        m=e.get("minutes")
        if m is None or not math.isfinite(float(m)) or not 0<=float(m)<=90:
            raise ValueError("Invalid minutes")
        days=(cutoff-t).total_seconds()/86400
        out.append((e,2**(-days/half_life_days)))
    return out

def infer_player_roles(events, cutoff, start_prior=.65, prior_exposure=8.,
                       starter_minutes_prior=77., duration_exposure=5.,
                       half_life_days=180., cameo_prior=.45,
                       cameo_minutes_prior=18.):
    """Infer soft roles from verified-available historical appearances.

    For every role weight, only prior observations enter. Labels represent
    probabilities of *being in a behavior band*, not unconditional starts.
    """
    if not all(math.isfinite(float(v)) for v in (start_prior,prior_exposure,starter_minutes_prior,duration_exposure,cameo_prior,cameo_minutes_prior)) or not 0<start_prior<1 or prior_exposure<=0 or duration_exposure<=0:
        raise ValueError("Invalid priors")
    if not 0<=starter_minutes_prior<=90: raise ValueError("Invalid minute prior")
    if not 0<=cameo_prior<=1 or not 0<=cameo_minutes_prior<=90:
        raise ValueError('Invalid cameo prior')
    rows=_weights(events,cutoff,half_life_days)
    starts=sum(w for e,w in rows if e["started"])
    benches=sum(w for e,w in rows if not e["started"])
    p=(start_prior*prior_exposure+starts)/(prior_exposure+starts+benches)
    starter_denom=duration_exposure+starts
    duration=(starter_minutes_prior*duration_exposure+
              sum(float(e["minutes"])*w for e,w in rows if e["started"]))/starter_denom
    cameos=sum(w for e,w in rows if not e["started"] and e["minutes"]>0)
    q=(cameo_prior*prior_exposure+cameos)/(prior_exposure+benches)
    cm=(cameo_minutes_prior*duration_exposure+sum(float(e['minutes'])*w for e,w in rows if not e['started'] and e['minutes']>0))/(duration_exposure+cameos)
    # Start weights sum to one; duration weights separately sum to one.
    starter_role={"regular_starter":p,"rotation_or_bench":1-p}
    duration_role={"long_stint_starter":duration/90.,
                   "early_substitution_starter":1-duration/90.}
    return {"p_start_given_available":p,
            "starter_minutes_mean":duration,
            "p_cameo_given_bench":q,
            "cameo_minutes_mean":cm,
            "start_roles":starter_role,
            "starter_duration_roles":duration_role,
            "effective_start_observations":starts+benches,
            "effective_starter_observations":starts,
            "uncertainty_note":"Heuristic smoothed role weights; NOT calibrated posteriors",
            "research_only":True}

