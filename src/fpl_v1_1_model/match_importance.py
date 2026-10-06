"""Cutoff-safe Match Importance primitives for P(start).

Match Importance contains only:
1) dynamic competition value,
2) round/stage strength,
3) opponent strength.

It must not be added as the same player-level intercept for everybody. The
minute model should use these values to modulate role hierarchy H.
"""
from __future__ import annotations
from math import exp
from typing import Mapping, Sequence

BASE_COMPETITION_VALUES = {
    "prem": 1.00,
    "champions-league": 0.95,
    "europa-league": 0.70,
    "conference-league": 0.50,
    "fa-cup": 0.55,
    "efl-cup": 0.35,
}

ALIASES = {
    "premier-league": "prem", "prem": "prem",
    "champions league": "champions-league", "champions-league": "champions-league",
    "uefa champions league": "champions-league",
    "europa league": "europa-league", "europa-league": "europa-league",
    "uefa europa league": "europa-league",
    "conference league": "conference-league", "conference-league": "conference-league",
    "uefa conference league": "conference-league",
    "fa cup": "fa-cup", "fa-cup": "fa-cup",
    "efl cup": "efl-cup", "efl-cup": "efl-cup", "league cup": "efl-cup",
}


def canonical_competition(value: str) -> str:
    raw = str(value or "").strip().lower().replace("_", "-")
    return ALIASES.get(raw, raw)


def dynamic_competition_value(
    competition: str,
    active_competitions: Sequence[str],
    base_values: Mapping[str, float] = BASE_COMPETITION_VALUES,
    *,
    eta: float = 0.35,
) -> float:
    """Raise the value of remaining opportunities as other competitions end."""
    competition = canonical_competition(competition)
    b = float(base_values.get(competition, 0.0))
    if b <= 0:
        return 0.0
    active = [canonical_competition(c) for c in active_competitions]
    active = [c for c in active if float(base_values.get(c, 0.0)) > 0]
    if competition not in active:
        active.append(competition)
    denom = sum(float(base_values[c]) for c in set(active)) or b
    reference = sum(float(v) for v in base_values.values() if float(v) > 0) or denom
    return b * (reference / denom) ** float(eta)


def premier_league_stage_strength(gw: int) -> float:
    """Smooth stage value: late-season league matches carry more hierarchy signal."""
    g = min(38, max(1, int(gw)))
    progress = (g - 1) / 37.0
    return 0.20 + 0.80 * progress ** 1.5


def knockout_stage_strength(round_name: str | None, kickoff_month: int | None = None) -> float:
    s = str(round_name or "").lower()
    table = [
        (("final",), 1.00),
        (("semi",), 0.88),
        (("quarter",), 0.76),
        (("round of 16", "last 16", "fifth round"), 0.64),
        (("fourth round", "round 4"), 0.50),
        (("third round", "round 3"), 0.40),
        (("playoff", "play-off"), 0.55),
        (("league phase", "group"), 0.36),
    ]
    for keys, value in table:
        if any(k in s for k in keys):
            return value
    if kickoff_month is not None:
        # Conservative fallback when the source has no explicit stage label.
        if kickoff_month >= 5:
            return 0.90
        if kickoff_month == 4:
            return 0.78
        if kickoff_month == 3:
            return 0.64
        if kickoff_month == 2:
            return 0.52
        if kickoff_month == 1:
            return 0.42
    return 0.35


def opponent_strength_from_elo(elo: float | None, midpoint: float = 1800.0, scale: float = 180.0) -> float:
    if elo is None:
        return 0.5
    try:
        x = float(elo)
    except (TypeError, ValueError):
        return 0.5
    if x != x:
        return 0.5
    z = max(-8.0, min(8.0, (x - midpoint) / scale))
    return 1.0 / (1.0 + exp(-z))


def hierarchy_interactions(h_fast: float, h_slow: float, competition_value: float,
                           stage_strength: float, opponent_strength: float) -> dict[str, float]:
    """Only hierarchy interactions; no team-wide additive importance term."""
    return {
        "mi_h_fast_comp": float(h_fast) * float(competition_value),
        "mi_h_fast_stage": float(h_fast) * float(stage_strength),
        "mi_h_fast_opp": float(h_fast) * float(opponent_strength),
        "mi_h_slow_comp": float(h_slow) * float(competition_value),
        "mi_h_slow_stage": float(h_slow) * float(stage_strength),
        "mi_h_slow_opp": float(h_slow) * float(opponent_strength),
    }
