"""Experimental individual role-state filter for MM start probability.

An optional, strictly pre-cutoff filter. Not calibrated; never changes locked MM.
Only observed starts while VERIFIED AVAILABLE should update the underlying role.
"""
from __future__ import annotations
import math


def role_start_probability(observations, prior=.75, strength=8.,
                           half_life_days=120., cutoff=None):
    """Beta-style decayed role estimate from (known_at, started, available) rows.

    Missing or unavailable games do not count as evidence of role loss.
    This is a *role prior*, not a complete availability/start prediction.
    """
    if not all(math.isfinite(float(v)) for v in (prior,strength,half_life_days)) or not (0 < prior < 1 and strength > 0 and half_life_days > 0):
        raise ValueError("Invalid model settings")
    if cutoff is None:
        raise ValueError("Cutoff required")
    successes=prior*strength
    exposure=strength
    accepted=0
    last=None
    for obs in sorted(observations,key=lambda x:x["known_at"]):
        known=obs["known_at"]
        if known >= cutoff:
            continue
        if obs.get("available") is not True:
            continue
        if last is not None and known == last:
            raise ValueError("Duplicate observation timestamp")
        started=obs.get("started")
        if started not in (True,False):
            raise ValueError("Invalid started observation")
        days=(cutoff-known).total_seconds()/86400.
        w=2.**(-days/half_life_days)
        successes+=w*int(started)
        exposure+=w
        accepted+=1
        last=known
    value=successes/exposure
    return {"role_start_prior":value,"effective_observations":exposure-strength,
            "observations_used":accepted,"is_experiment":True}

