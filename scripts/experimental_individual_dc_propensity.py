"""Opt-in DC research: separate player action propensity from defensive exposure.

Input must be VERIFIED historical DC counts and 90-minute opportunities known
before the forecast cutoff. This is not a replacement for the existing soft-
role DC model. No source mixing, missing-event zero-fill, or production changes.
"""
from __future__ import annotations
import math


def player_dc_propensity(history, cutoff, role_rate90, prior_minutes=900.,
                         half_life_days=365.):
    """Shrunken DC action propensity per 90 opportunity-neutral minutes.

    Each observation: known_at, minutes, dc_count, exposure_multiplier.
    exposure_multiplier=1 is the neutral research ablation. Multipliers other
    than 1 require a strictly pre-match, verified workload exposure model.
    """
    if not (math.isfinite(role_rate90) and role_rate90>=0 and
            math.isfinite(prior_minutes) and prior_minutes>0 and
            math.isfinite(half_life_days) and half_life_days>0):
        raise ValueError("Invalid role DC prior")
    num=role_rate90*prior_minutes/90.
    den=prior_minutes/90.
    used=0
    for obs in history:
        known=obs["known_at"]
        if known>cutoff:
            continue
        mins=float(obs["minutes"])
        count=float(obs["dc_count"])
        multiplier=float(obs.get("exposure_multiplier",1.))
        if not (math.isfinite(mins) and 0<=mins<=90 and
                math.isfinite(count) and count>=0 and count.is_integer() and
                math.isfinite(multiplier) and multiplier>0):
            raise ValueError("Invalid historical DC observation")
        weight=2.**(-((cutoff-known).total_seconds()/86400.)/half_life_days)
        num+=weight*count
        den+=weight*(mins/90.)*multiplier
        used+=1
    rate=num/den
    return {"neutral_dc_rate90":rate,"effective_exposure90":den-prior_minutes/90.,
            "observations_used":used,"research_only":True}


def projected_dc_mean(neutral_dc_rate90, expected_minutes, opponent_opportunity=1.):
    """Translate profile into DC count expectation; not a threshold probability."""
    v=(neutral_dc_rate90,expected_minutes,opponent_opportunity)
    if not all(math.isfinite(float(x)) for x in v):
        raise ValueError("Nonfinite DC projection")
    if neutral_dc_rate90<0 or not 0<=expected_minutes<=90 or opponent_opportunity<=0:
        raise ValueError("Invalid DC projection inputs")
    return neutral_dc_rate90*(expected_minutes/90.)*opponent_opportunity
