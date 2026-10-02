"""P(start) v2 experimental model.

Three top-level blocks only:
  1) Match importance = competition value + round/stage + opponent strength
  2) Minutes = recent starts/minutes + short-term workload
  3) Position/Role = role share q + slowly changing hierarchy H

The final allocation is constrained so each player starts at most once and the
team has exactly 11 expected starters (1 GK + 10 outfield).

This module is deliberately independent from FPL chance-of-playing/availability.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from typing import Dict, Iterable, Mapping, Sequence, Tuple

EPS = 1e-8


def sigmoid(x: float) -> float:
    if x >= 0:
        z = exp(-x)
        return 1.0 / (1.0 + z)
    z = exp(x)
    return z / (1.0 + z)


def logit(p: float) -> float:
    p = min(1.0-EPS, max(EPS, float(p)))
    return log(p/(1.0-p))


def recency_weight(lag: float, half_life: float) -> float:
    if half_life <= 0:
        raise ValueError("half_life must be positive")
    return 2.0 ** (-float(lag)/float(half_life))


@dataclass(frozen=True)
class MatchImportanceParams:
    intercept: float = -1.0
    competition_coef: float = 1.0
    round_coef: float = 1.0
    opponent_coef: float = 1.0
    scarcity_eta: float = 0.35


def dynamic_competition_value(
    competition: str,
    active_competitions: Sequence[str],
    base_values: Mapping[str, float],
    *,
    eta: float = 0.35,
) -> float:
    """Dynamic value for a competition as other trophy opportunities disappear.

    PL remains part of the active opportunity set.  The scale is anchored to
    the sum of base values for the maximal competition set provided by the
    caller, so the dynamic term is interpretable and monotone.
    """
    b = float(base_values.get(competition, 0.0))
    if b <= 0:
        return 0.0
    active = [c for c in active_competitions if float(base_values.get(c, 0.0)) > 0]
    denom = sum(float(base_values[c]) for c in active) or b
    reference = sum(float(v) for v in base_values.values() if float(v) > 0) or denom
    scarcity = (reference / denom) ** float(eta)
    return b * scarcity


def match_importance(
    *,
    competition: str,
    active_competitions: Sequence[str],
    round_strength: float,
    opponent_strength: float,
    base_values: Mapping[str, float],
    params: MatchImportanceParams = MatchImportanceParams(),
) -> float:
    cv = dynamic_competition_value(
        competition, active_competitions, base_values, eta=params.scarcity_eta
    )
    x = (
        params.intercept
        + params.competition_coef * cv
        + params.round_coef * min(1.0, max(0.0, float(round_strength)))
        + params.opponent_coef * min(1.0, max(0.0, float(opponent_strength)))
    )
    return sigmoid(x)


@dataclass
class HierarchyState:
    positive: float = 1.0
    negative: float = 1.0

    @property
    def value(self) -> float:
        den = self.positive + self.negative
        return self.positive / den if den > 0 else 0.5

    def update(
        self,
        *,
        started: bool,
        minutes: float,
        importance: float,
        role_share: float = 1.0,
        in_matchday_squad: bool | None = True,
        half_life: float = 10.0,
        cameo_credit: float = 0.30,
        min_importance_weight: float = 0.25,
    ) -> None:
        # Unknown/out-of-squad rows should not be interpreted as losing hierarchy.
        decay = recency_weight(1.0, half_life)
        self.positive *= decay
        self.negative *= decay
        if in_matchday_squad is False:
            return
        imp = min(1.0, max(0.0, float(importance)))
        w = min_importance_weight + (1.0-min_importance_weight)*imp
        q = min(1.0, max(0.0, float(role_share)))
        if started:
            evidence = 1.0
        else:
            evidence = cameo_credit * min(1.0, max(0.0, float(minutes)/90.0))
        self.positive += w*q*evidence
        self.negative += w*q*(1.0-evidence)


@dataclass(frozen=True)
class MinutesFeatures:
    recent_start: float
    slow_start: float
    recent_minutes_frac: float
    workload: float


def minutes_features(
    history: Iterable[Mapping[str, float]],
    *,
    fast_half_life: float = 3.0,
    slow_half_life: float = 10.0,
    minutes_half_life: float = 3.0,
    workload_tau_days: float = 5.0,
    fallback: float = 0.25,
) -> MinutesFeatures:
    rows = list(history)
    if not rows:
        return MinutesFeatures(fallback, fallback, fallback, 0.0)
    num_f = den_f = num_s = den_s = num_m = den_m = workload = 0.0
    # expected keys: lag_games, started, minutes, days_ago
    for r in rows:
        lag = max(1.0, float(r.get("lag_games", 1.0)))
        st = float(bool(r.get("started", 0)))
        mins = min(120.0, max(0.0, float(r.get("minutes", 0.0))))
        wf = recency_weight(lag, fast_half_life)
        ws = recency_weight(lag, slow_half_life)
        wm = recency_weight(lag, minutes_half_life)
        num_f += wf*st; den_f += wf
        num_s += ws*st; den_s += ws
        num_m += wm*(mins/90.0); den_m += wm
        days = max(0.0, float(r.get("days_ago", lag*7.0)))
        workload += (mins/90.0) * exp(-days/max(EPS, workload_tau_days))
    return MinutesFeatures(
        num_f/den_f if den_f else fallback,
        num_s/den_s if den_s else fallback,
        num_m/den_m if den_m else fallback,
        workload,
    )


@dataclass(frozen=True)
class PlayerRoleInput:
    player_id: str
    role: str
    role_share: float
    hierarchy: float
    minutes: MinutesFeatures
    is_goalkeeper: bool = False


@dataclass(frozen=True)
class ScoreParams:
    recent_start_coef: float = 1.0
    slow_start_coef: float = 1.0
    minutes_coef: float = 1.0
    workload_coef: float = 0.25
    role_share_coef: float = 0.35
    hierarchy_base_coef: float = 0.75
    hierarchy_importance_coef: float = 1.0


def player_role_score(x: PlayerRoleInput, importance: float, params: ScoreParams) -> float:
    q = min(1.0, max(EPS, float(x.role_share)))
    h = min(1.0-EPS, max(EPS, float(x.hierarchy)))
    m = x.minutes
    return (
        params.recent_start_coef*logit(m.recent_start)
        + params.slow_start_coef*logit(m.slow_start)
        + params.minutes_coef*(m.recent_minutes_frac-0.5)
        - params.workload_coef*m.workload
        + params.role_share_coef*log(q)
        + (params.hierarchy_base_coef + params.hierarchy_importance_coef*float(importance))*logit(h)
    )


def _solve_player_role_transport(
    scores: Mapping[Tuple[str,str], float],
    role_capacity: Mapping[str, float],
    *,
    temperature: float = 1.0,
    max_iter: int = 1000,
    tol: float = 1e-10,
) -> Dict[Tuple[str,str], float]:
    """Entropy-regularised soft assignment with role capacities and player cap <=1.

    Iterative scaling alternates exact role-column capacities with player row caps.
    It converges to the KL/entropy projection for positive kernels and is enough
    for the small squad matrices used here.
    """
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    players = sorted({p for p,_ in scores})
    roles = sorted(role_capacity)
    x = {(p,r): exp(max(-40.0, min(40.0, scores.get((p,r), -40.0)/temperature)))
         for p in players for r in roles}
    for _ in range(max_iter):
        old = dict(x)
        # exact role capacity
        for r in roles:
            s = sum(x[p,r] for p in players)
            cap = float(role_capacity[r])
            if cap < 0:
                raise ValueError("role capacity must be non-negative")
            f = cap/s if s > 0 else 0.0
            for p in players: x[p,r] *= f
        # each player at most one starting slot
        for p in players:
            s = sum(x[p,r] for r in roles)
            if s > 1.0:
                f = 1.0/s
                for r in roles: x[p,r] *= f
        err = max(abs(x[k]-old[k]) for k in x) if x else 0.0
        if err < tol:
            break
    # final column balancing; iterate a few more with row cap to preserve both.
    for _ in range(100):
        for r in roles:
            s=sum(x[p,r] for p in players); cap=float(role_capacity[r])
            f=cap/s if s>0 else 0.0
            for p in players: x[p,r]*=f
        violated=False
        for p in players:
            s=sum(x[p,r] for r in roles)
            if s>1.0+1e-10:
                violated=True; f=1.0/s
                for r in roles: x[p,r]*=f
        if not violated: break
    return x


def constrained_start_probabilities(
    inputs: Sequence[PlayerRoleInput],
    *,
    importance: float,
    role_capacity: Mapping[str, float],
    params: ScoreParams = ScoreParams(),
    temperature: float = 1.0,
) -> tuple[Dict[str,float], Dict[Tuple[str,str],float]]:
    """Return player P(start) and player-role assignment.

    Call GK and outfield separately if desired.  Capacities should sum to the
    required number of starters (1 for GK, 10 for outfield).
    """
    score_map={(x.player_id,x.role):player_role_score(x,importance,params) for x in inputs}
    alloc=_solve_player_role_transport(score_map,role_capacity,temperature=temperature)
    p={pid:0.0 for pid in {x.player_id for x in inputs}}
    for (pid,_),v in alloc.items(): p[pid]+=v
    return p,alloc
