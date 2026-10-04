"""Reusable v1.1 player-attack allocation primitives.

The historical experiment estimates a player's current-season xG/xA rate,
shrinks only to a current-season position prior, converts the rate to a fixture
propensity with xMins, then normalizes player propensities to an independently
forecast team event total.  This prevents team strength and player xG from
being counted twice.
"""
from __future__ import annotations
from typing import Iterable


def shrunk_rate_per90(weighted_events: float, weighted_minutes: float, prior_rate_per90: float, prior_minutes_tau: float) -> float:
    if weighted_events < 0 or weighted_minutes < 0 or prior_rate_per90 < 0 or prior_minutes_tau < 0:
        raise ValueError("attack inputs must be non-negative")
    den=weighted_minutes+prior_minutes_tau
    if den <= 0:
        return float(prior_rate_per90)
    return 90.0*(weighted_events + prior_minutes_tau*prior_rate_per90/90.0)/den


def event_propensity(expected_minutes: float, rate_per90: float) -> float:
    if expected_minutes < 0 or rate_per90 < 0:
        raise ValueError("expected_minutes and rate_per90 must be non-negative")
    return expected_minutes/90.0*rate_per90


def allocate_team_event_mean(team_event_mean: float, propensities: Iterable[float]) -> list[float]:
    if team_event_mean < 0:
        raise ValueError("team_event_mean must be non-negative")
    p=[float(x) for x in propensities]
    if any(x < 0 for x in p):
        raise ValueError("propensities must be non-negative")
    total=sum(p)
    if total <= 0:
        return [0.0 for _ in p]
    return [team_event_mean*x/total for x in p]
