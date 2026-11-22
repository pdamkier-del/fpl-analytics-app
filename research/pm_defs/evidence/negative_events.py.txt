"""Negative-event primitives for the FPL v1.1 event model.

Direct negative FPL events are deliberately represented separately from BPS:
- yellow card: -1 FPL point
- red card: -3 FPL points
- own goal: -2 FPL points
- penalty miss: -2 FPL points (kept for the later shared penalty event model)

Yellow and red are a *competing* discipline outcome for a player-fixture.  The
historical FPL core exposes final FPL yellow/red flags but not a reliable split
between straight reds and second-yellow reds, so the historical-core candidate
does not pretend to know that subtype.  Live Rich can add it later.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import exp
from typing import Any


@dataclass(frozen=True)
class DisciplineProbabilities:
    none: float
    yellow: float
    red: float

    def __post_init__(self) -> None:
        vals=(self.none,self.yellow,self.red)
        if any(v < -1e-12 or v > 1+1e-12 for v in vals):
            raise ValueError("discipline probabilities must be in [0,1]")
        if abs(sum(vals)-1.0) > 1e-8:
            raise ValueError("discipline probabilities must sum to 1")


def competing_card_probabilities(
    expected_minutes: float,
    yellow_rate90: float,
    red_rate90: float,
    *,
    yellow_multiplier: float=1.0,
    red_multiplier: float=1.0,
) -> DisciplineProbabilities:
    """Convert cause-specific card hazards into a categorical fixture outcome.

    The two hazards compete for one FPL discipline outcome.  This matches the
    normalized Historical Core where a fixture row never simultaneously carries
    both ``yellow_cards`` and ``fpl_red_cards``.  A second-yellow dismissal is
    therefore represented by the final red outcome, not by yellow + red points.
    """
    m=float(expected_minutes)
    yr=float(yellow_rate90)*float(yellow_multiplier)
    rr=float(red_rate90)*float(red_multiplier)
    if m < 0 or yr < 0 or rr < 0:
        raise ValueError("minutes and rates/multipliers must be non-negative")
    exposure=min(90.0,m)/90.0
    total=(yr+rr)*exposure
    if total <= 0:
        return DisciplineProbabilities(1.0,0.0,0.0)
    p_any=1.0-exp(-total)
    p_y=p_any*yr/(yr+rr)
    p_r=p_any*rr/(yr+rr)
    return DisciplineProbabilities(1.0-p_any,p_y,p_r)


def rare_event_probability(expected_minutes: float, rate90: float) -> float:
    """At-least-one probability for a rare per-90 Poisson event."""
    m=float(expected_minutes); r=float(rate90)
    if m < 0 or r < 0:
        raise ValueError("minutes and rate90 must be non-negative")
    return 1.0-exp(-r*min(90.0,m)/90.0)


def direct_negative_points(
    *,
    yellow: int=0,
    red: int=0,
    own_goal: int=0,
    penalty_miss: int=0,
) -> int:
    """Official direct FPL deductions, excluding GK/DEF goals conceded."""
    vals=(yellow,red,own_goal,penalty_miss)
    if any(int(v) < 0 for v in vals):
        raise ValueError("event counts must be non-negative")
    return -int(yellow)-3*int(red)-2*int(own_goal)-2*int(penalty_miss)


def expected_direct_negative_points(
    discipline: DisciplineProbabilities,
    *,
    p_own_goal: float=0.0,
    p_penalty_miss: float=0.0,
) -> float:
    """Expected direct deduction from mutually-exclusive cards + rare events."""
    if not 0 <= p_own_goal <= 1 or not 0 <= p_penalty_miss <= 1:
        raise ValueError("rare-event probabilities must be in [0,1]")
    return -discipline.yellow-3.0*discipline.red-2.0*p_own_goal-2.0*p_penalty_miss


def sample_discipline(rng: Any, p: DisciplineProbabilities) -> str:
    """Draw ``none``, ``yellow`` or ``red`` from a NumPy-like RNG."""
    u=float(rng.random())
    if u < p.red:
        return "red"
    if u < p.red+p.yellow:
        return "yellow"
    return "none"


@dataclass(frozen=True)
class LeagueDisciplineState:
    """Suspension state for multi-fixture availability propagation.

    Yellow accumulation bans are competition-specific to the Premier League.
    Red-card bans are different: they are normally served across first-team
    domestic league/cup fixtures.  Keeping two counters prevents the simulator
    from incorrectly treating a cup-served red ban as a future PL absence.
    """
    yellows: int=0
    served_five: bool=False
    served_ten: bool=False
    served_fifteen: bool=False
    league_yellow_ban_matches: int=0
    all_domestic_ban_matches: int=0


def add_league_yellow(state: LeagueDisciplineState, club_league_match_number: int) -> LeagueDisciplineState:
    """Apply one PL caution and trigger the 2026/27 accumulation sanction."""
    n=int(club_league_match_number)
    if n < 1 or n > 38:
        raise ValueError("club_league_match_number must be 1..38")
    y=state.yellows+1; ban=state.league_yellow_ban_matches
    f,t,ft=state.served_five,state.served_ten,state.served_fifteen
    if y >= 5 and n <= 19 and not f:
        ban+=1; f=True
    if y >= 10 and n <= 32 and not t:
        ban+=2; t=True
    if y >= 15 and not ft:
        ban+=3; ft=True
    return LeagueDisciplineState(y,f,t,ft,ban,state.all_domestic_ban_matches)


_RED_BASE_SUSPENSIONS={
    "dogso_handball":1,
    "dogso_free_kick":1,
    "serious_foul_play":3,
    "spitting":6,
    "violent_conduct":3,
    "offensive_language_or_gestures":2,
    "second_caution":1,
}

def red_suspension_matches(offence: str, dismissal_number: int=1) -> int:
    """2026/27 FA automatic red-card suspension length.

    A second dismissal in the season adds one match, a third adds two, etc.
    Exceptional/retrospective sanctions must still come from authoritative data.
    """
    if offence not in _RED_BASE_SUSPENSIONS:
        raise ValueError("unknown red-card offence; authoritative subtype required")
    d=int(dismissal_number)
    if d < 1: raise ValueError("dismissal_number must be >=1")
    return _RED_BASE_SUSPENSIONS[offence]+(d-1)


def add_known_red_suspension(state: LeagueDisciplineState, suspension_matches: int) -> LeagueDisciplineState:
    """Add an authoritative cross-domestic red-card suspension length."""
    n=int(suspension_matches)
    if n < 0: raise ValueError("suspension_matches must be non-negative")
    return LeagueDisciplineState(state.yellows,state.served_five,state.served_ten,state.served_fifteen,state.league_yellow_ban_matches,state.all_domestic_ban_matches+n)


def unavailable_for_next_pl_fixture(state: LeagueDisciplineState) -> bool:
    return state.league_yellow_ban_matches>0 or state.all_domestic_ban_matches>0


def serve_league_match(state: LeagueDisciplineState) -> LeagueDisciplineState:
    """Advance one Premier League fixture while suspended."""
    return LeagueDisciplineState(state.yellows,state.served_five,state.served_ten,state.served_fifteen,max(0,state.league_yellow_ban_matches-1),max(0,state.all_domestic_ban_matches-1))


def serve_domestic_cup_match(state: LeagueDisciplineState) -> LeagueDisciplineState:
    """Advance one eligible domestic cup fixture; yellow PL bans do not move."""
    return LeagueDisciplineState(state.yellows,state.served_five,state.served_ten,state.served_fifteen,state.league_yellow_ban_matches,max(0,state.all_domestic_ban_matches-1))
