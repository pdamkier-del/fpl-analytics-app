"""Current-season-only recency-weighted minutes/role model for FPL v1.1.

This module intentionally has no dependency on previous-season player data.
Availability/team-news is a separate forecast-state layer and can be applied with
``availability``. Historical Core lacks reliable absence reasons, so historical
backtests using all fixture rows are explicitly availability-inclusive.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import exp, log
from typing import Iterable, Mapping, Any

@dataclass(frozen=True)
class MinutesProjection:
    p_start: float
    p_cameo_given_bench: float
    p_play: float
    p_60: float
    expected_minutes: float
    expected_minutes_given_start: float
    expected_minutes_given_cameo: float
    effective_fixture_weight: float
    n_prior_fixtures: int
    availability: float


def _weight(lag: int, half_life: float) -> float:
    if half_life <= 0:
        raise ValueError("half_life must be > 0")
    return exp(-log(2.0) * lag / half_life)


def _mean(pairs: list[tuple[float, float]], fallback: float) -> float:
    den = sum(w for w, _ in pairs)
    return sum(w * x for w, x in pairs) / den if den > 0 else fallback


def project_minutes(
    history: Iterable[Mapping[str, Any]],
    *,
    role_half_life: float = 1.0,
    duration_half_life: float = 1.5,
    availability: float = 1.0,
    fallback_start_minutes: float = 78.0,
    fallback_cameo_minutes: float = 16.0,
    fallback_p_start: float = 0.25,
    fallback_p_cameo: float = 0.20,
    start_logit_intercept: float | None = None,
    start_logit_slope: float | None = None,
) -> MinutesProjection:
    """Project minutes from prior current-season fixture rows only.

    ``history`` must be oldest -> newest and contain ``started`` and ``minutes``.
    A zero-minute fixture remains informative for role in Historical Core. When
    reliable matchday-squad/absence labels exist, callers may filter genuinely
    unavailable fixtures before calling this function.
    """
    rows = list(history)
    availability = min(1.0, max(0.0, float(availability)))
    if not rows:
        p_start = fallback_p_start
        p_cameo = fallback_p_cameo
        sm = fallback_start_minutes
        cm = fallback_cameo_minutes
        p60_start = 0.85
        p60_cameo = 0.0
        eff = 0.0
    else:
        role=[]; starts=[]; nonstarts=[]; cameos=[]; start60=[]; cameo60=[]
        for lag, r in enumerate(reversed(rows)):
            st = int(r["started"] or 0)
            mins = float(r["minutes"] or 0.0)
            wr = _weight(lag, role_half_life)
            wd = _weight(lag, duration_half_life)
            role.append((wr, float(st)))
            if st:
                starts.append((wd, mins)); start60.append((wd, float(mins >= 60)))
            else:
                nonstarts.append((wr, float(mins > 0)))
                if mins > 0:
                    cameos.append((wd, mins)); cameo60.append((wd, float(mins >= 60)))
        p_start = _mean(role, fallback_p_start)
        p_cameo = _mean(nonstarts, fallback_p_cameo)
        sm = _mean(starts, fallback_start_minutes)
        cm = _mean(cameos, fallback_cameo_minutes)
        p60_start = _mean(start60, 0.85)
        p60_cameo = _mean(cameo60, 0.0)
        eff = sum(w for w, _ in role)

    # Optional temperature/logit regularization.  This is fitted only on
    # historical development seasons; it softens overconfident recency
    # probabilities without importing a previous-season player prior.
    if (start_logit_intercept is None) != (start_logit_slope is None):
        raise ValueError("start_logit_intercept and start_logit_slope must be supplied together")
    if start_logit_intercept is not None:
        eps=1e-6
        q=min(1.0-eps,max(eps,p_start))
        z=float(start_logit_intercept)+float(start_logit_slope)*log(q/(1.0-q))
        p_start=1.0/(1.0+exp(-z))

    raw_play = p_start + (1.0 - p_start) * p_cameo
    raw_60 = p_start * p60_start + (1.0 - p_start) * p_cameo * p60_cameo
    raw_minutes = p_start * sm + (1.0 - p_start) * p_cameo * cm
    return MinutesProjection(
        p_start=availability * p_start,
        p_cameo_given_bench=p_cameo,
        p_play=availability * raw_play,
        p_60=availability * raw_60,
        expected_minutes=availability * raw_minutes,
        expected_minutes_given_start=sm,
        expected_minutes_given_cameo=cm,
        effective_fixture_weight=eff,
        n_prior_fixtures=len(rows),
        availability=availability,
    )
