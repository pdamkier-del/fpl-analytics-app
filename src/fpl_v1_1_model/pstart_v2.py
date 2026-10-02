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

# ---------------------------------------------------------------------------
# Deadline-state availability and role-aware start allocation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AvailabilityState:
    """Cutoff-safe availability state known at the forecast deadline.

    status is descriptive; probability_available is the mathematical cap used by
    the assignment solver.  Injury/suspension information changes the current
    allocation but does not mutate role share q or hierarchy H.
    """
    status: str = "unknown"
    probability_available: float = 1.0
    reason: str | None = None
    observed_at: str | None = None

    @property
    def cap(self) -> float:
        s = (self.status or "unknown").strip().lower()
        if s in {"injured", "suspended", "unavailable", "ineligible", "out"}:
            return 0.0
        return min(1.0, max(0.0, float(self.probability_available)))


def availability_from_status(
    status: str | None,
    chance_of_playing: float | None = None,
    *,
    reason: str | None = None,
    observed_at: str | None = None,
) -> AvailabilityState:
    """Map a timestamped status snapshot to a solver availability cap.

    Deterministic out/suspended states are zero. A source status explicitly saying
    the player is available is authoritative and ignores stale chance values. For
    unresolved/doubtful states, an explicit source chance can cap availability.
    """
    s = (status or "unknown").strip().lower()
    if s in {"injured", "suspended", "unavailable", "ineligible", "out"}:
        p = 0.0
    elif s in {"available", "a", "fit"}:
        # FPL can retain stale chance_of_playing values after a player has returned
        # to status=available. Historical audit shows those stale values must not
        # cap an otherwise available player. The status flag is authoritative here.
        p = 1.0
    elif chance_of_playing is not None:
        c = float(chance_of_playing)
        p = c / 100.0 if c > 1.0 else c
    else:
        p = 1.0
    return AvailabilityState(s, min(1.0, max(0.0, p)), reason, observed_at)


def deadline_state_before(rows: Iterable[Mapping], deadline) -> Mapping | None:
    """Return latest observation at/before deadline without looking forward.

    `deadline` and row['observed_at'] may be datetime-like or ISO strings.
    Imported lazily to keep the core dependency-light.
    """
    from datetime import datetime, timezone

    def parse(v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        s = str(v).replace("Z", "+00:00")
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

    cut = parse(deadline)
    if cut is None:
        raise ValueError("deadline is required")
    best = None
    best_t = None
    for row in rows:
        t = parse(row.get("observed_at"))
        if t is None or t > cut:
            continue
        if best_t is None or t > best_t:
            best, best_t = row, t
    return best


def _solve_player_role_transport_with_caps(
    scores: Mapping[Tuple[str, str], float],
    role_capacity: Mapping[str, float],
    player_capacity: Mapping[str, float],
    *,
    temperature: float = 1.0,
    max_iter: int = 3000,
    tol: float = 1e-11,
) -> Dict[Tuple[str, str], float]:
    """Entropy-regularised role assignment with role totals and player caps.

    Columns (roles) have exact required mass; rows (players) are capped by their
    deadline availability. This means an injured first-choice player keeps H but
    receives zero current start mass, which flows to the next role candidates.
    """
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    players = sorted({p for p, _ in scores})
    roles = sorted(role_capacity)
    total_need = sum(max(0.0, float(v)) for v in role_capacity.values())
    total_cap = sum(min(1.0, max(0.0, float(player_capacity.get(p, 1.0)))) for p in players)
    if total_cap + 1e-9 < total_need:
        raise ValueError(f"infeasible availability caps: need {total_need:.3f}, have {total_cap:.3f}")

    x = {}
    for p in players:
        pc = min(1.0, max(0.0, float(player_capacity.get(p, 1.0))))
        for r in roles:
            if pc <= 0 or (p, r) not in scores:
                x[p, r] = 0.0
            else:
                x[p, r] = exp(max(-40.0, min(40.0, scores[p, r] / temperature)))

    for _ in range(max_iter):
        old = dict(x)
        # exact role demand
        for r in roles:
            cap = max(0.0, float(role_capacity[r]))
            s = sum(x[p, r] for p in players)
            if cap > 0 and s <= 0:
                raise ValueError(f"role {r} has positive capacity but no available candidates")
            f = cap / s if s > 0 else 0.0
            for p in players:
                x[p, r] *= f
        # deadline player caps
        for p in players:
            cap = min(1.0, max(0.0, float(player_capacity.get(p, 1.0))))
            s = sum(x[p, r] for r in roles)
            if s > cap + 1e-15:
                f = cap / s if s > 0 else 0.0
                for r in roles:
                    x[p, r] *= f
        err = max((abs(x[k] - old[k]) for k in x), default=0.0)
        col_err = max((abs(sum(x[p, r] for p in players) - float(role_capacity[r])) for r in roles), default=0.0)
        if err < tol and col_err < 1e-9:
            break

    # final feasibility check; don't silently claim exact-11 if caps prevent it
    col_err = max((abs(sum(x[p, r] for p in players) - float(role_capacity[r])) for r in roles), default=0.0)
    row_err = max((sum(x[p, r] for r in roles) - float(player_capacity.get(p, 1.0)) for p in players), default=0.0)
    if col_err > 1e-6 or row_err > 1e-6:
        # Rare hard-cap cases (for example an injured first-choice player) can
        # make simple iterative scaling converge very slowly. Fall back to a
        # small convex SLSQP solve so exact role totals are preserved rather
        # than silently accepting an almost-XI.
        try:
            import numpy as np
            from scipy.optimize import minimize
            keys=[(p,r) for p in players for r in roles if (p,r) in scores and player_capacity.get(p,1.0)>0]
            if not keys:
                raise ValueError("no available player-role edges")
            idx={k:i for i,k in enumerate(keys)}
            z0=np.array([max(1e-10,x.get(k,1e-10)) for k in keys],dtype=float)
            # Rebalance the starting point approximately before SLSQP.
            for r in roles:
                ii=[idx[(p,r)] for p in players if (p,r) in idx]
                if ii:
                    ss=z0[ii].sum(); cap=float(role_capacity[r])
                    if ss>0: z0[ii]*=cap/ss
            score_vec=np.array([scores[k]/temperature for k in keys],dtype=float)
            def obj(z):
                zz=np.maximum(z,1e-15)
                return float(np.sum(zz*np.log(zz)-score_vec*zz))
            cons=[]
            for r in roles:
                ii=np.array([idx[(p,r)] for p in players if (p,r) in idx],dtype=int)
                cap=float(role_capacity[r])
                cons.append({'type':'eq','fun':lambda z,ii=ii,cap=cap: float(z[ii].sum()-cap)})
            for p in players:
                ii=np.array([idx[(p,r)] for r in roles if (p,r) in idx],dtype=int)
                cap=min(1.0,max(0.0,float(player_capacity.get(p,1.0))))
                if len(ii):
                    cons.append({'type':'ineq','fun':lambda z,ii=ii,cap=cap: float(cap-z[ii].sum())})
            res=minimize(obj,z0,method='SLSQP',bounds=[(0.0,None)]*len(keys),constraints=cons,
                         options={'ftol':1e-12,'maxiter':2000,'disp':False})
            if not res.success:
                raise ValueError(res.message)
            x={(p,r):0.0 for p in players for r in roles}
            for k,v in zip(keys,res.x): x[k]=float(max(0.0,v))
            col_err=max((abs(sum(x[p,r] for p in players)-float(role_capacity[r])) for r in roles),default=0.0)
            row_err=max((sum(x[p,r] for r in roles)-float(player_capacity.get(p,1.0)) for p in players),default=0.0)
        except Exception as exc:
            raise ValueError(f"role transport did not converge: col_err={col_err:.3g}, row_err={row_err:.3g}; fallback={exc}") from exc
    if col_err > 1e-6 or row_err > 1e-6:
        raise ValueError(f"role transport did not converge after fallback: col_err={col_err:.3g}, row_err={row_err:.3g}")
    return x


def constrained_start_probabilities_deadline(
    inputs: Sequence[PlayerRoleInput],
    *,
    importance: float,
    role_capacity: Mapping[str, float],
    availability: Mapping[str, AvailabilityState | float] | None = None,
    params: ScoreParams = ScoreParams(),
    temperature: float = 1.0,
) -> tuple[Dict[str, float], Dict[Tuple[str, str], float]]:
    """Deadline-safe role-aware P(start).

    Availability is a *cap*, not hierarchy evidence. Thus an injury changes the
    current XI probabilities without erasing what we know about the player's
    place in the role hierarchy.
    """
    availability = availability or {}
    score_map = {(x.player_id, x.role): player_role_score(x, importance, params) for x in inputs}
    players = {x.player_id for x in inputs}
    caps = {}
    for p in players:
        a = availability.get(p, 1.0)
        caps[p] = a.cap if isinstance(a, AvailabilityState) else min(1.0, max(0.0, float(a)))
    alloc = _solve_player_role_transport_with_caps(
        score_map, role_capacity, caps, temperature=temperature
    )
    p = {pid: 0.0 for pid in players}
    for (pid, _), v in alloc.items():
        p[pid] += v
    return p, alloc


def expected_minutes_from_start_probability(
    p_start: float,
    *,
    expected_minutes_if_start: float,
    p_cameo_if_bench: float,
    expected_minutes_if_cameo: float,
    availability_cap: float = 1.0,
) -> float:
    """Transparent xMins decomposition after role-aware P(start)."""
    ps = min(1.0, max(0.0, float(p_start)))
    av = min(1.0, max(0.0, float(availability_cap)))
    pc = min(1.0, max(0.0, float(p_cameo_if_bench)))
    starter = max(0.0, float(expected_minutes_if_start))
    cameo = max(0.0, float(expected_minutes_if_cameo))
    # p_start is already availability-capped. Bench cameo can only use remaining
    # available probability mass.
    bench_available = max(0.0, av - ps)
    return ps * starter + bench_available * pc * cameo

# ---------------------------------------------------------------------------
# Cold-start / new-signing priors
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColdStartPrior:
    """Cutoff-safe prior for a player newly joining a team.

    q_role and hierarchy_role are *priors*, not manual corrections. They should
    be estimated from information available before the deadline (previous-club
    role history and, optionally, a historically fitted transfer-context model).
    Their influence decays automatically as new-team evidence accumulates.
    """
    q_role: float
    hierarchy_role: float
    prior_equivalent_matches: float
    observed_at: str | None = None
    source_name: str | None = None


def bayes_blend_probability(
    observed_value: float,
    observed_evidence: float,
    prior_value: float,
    prior_evidence: float,
) -> float:
    """Empirical-Bayes blend of an observed probability-like state and prior.

    All quantities are evidence-weighted; no football correction factor is
    applied.  `prior_evidence` is a hyperparameter to be selected by historical
    CV (or supplied by a fitted cold-start model).
    """
    oe=max(0.0,float(observed_evidence)); pe=max(0.0,float(prior_evidence))
    ov=min(1.0,max(0.0,float(observed_value))); pv=min(1.0,max(0.0,float(prior_value)))
    den=oe+pe
    if den <= 0: return pv
    return min(1.0,max(0.0,(oe*ov+pe*pv)/den))


def blend_role_state_with_cold_prior(
    *,
    q_observed: float,
    q_evidence: float,
    hierarchy_observed: float,
    hierarchy_evidence: float,
    prior: ColdStartPrior | None,
) -> tuple[float,float]:
    """Blend role share q and role hierarchy H for a new/low-evidence player.

    As soon as new-team evidence grows, the prior weight falls mechanically.
    A player with no prior is returned unchanged.
    """
    if prior is None:
        return float(q_observed), float(hierarchy_observed)
    pe=max(0.0,float(prior.prior_equivalent_matches))
    q=bayes_blend_probability(q_observed,q_evidence,prior.q_role,pe)
    h=bayes_blend_probability(hierarchy_observed,hierarchy_evidence,prior.hierarchy_role,pe)
    return q,h


@dataclass(frozen=True)
class TransferContextCoefficients:
    """Coefficients of a historically fitted cold-start hierarchy model.

    The model intentionally receives raw, interpretable transfer features.  It
    does not encode rules such as 'expensive signing = starter'.  Coefficients
    must be fitted on past transfers and can be zero when a feature is absent.
    """
    intercept: float = 0.0
    previous_start_share: float = 0.0
    previous_minutes_share: float = 0.0
    fee_percentile_within_club: float = 0.0
    expectation_signal: float = 0.0
    age_centered: float = 0.0


def transfer_context_hierarchy_prior(
    *,
    previous_start_share: float = 0.0,
    previous_minutes_share: float = 0.0,
    fee_percentile_within_club: float = 0.0,
    expectation_signal: float = 0.0,
    age: float | None = None,
    age_reference: float = 25.0,
    coefficients: TransferContextCoefficients = TransferContextCoefficients(),
) -> float:
    """Return a learned hierarchy prior from pre-deadline transfer context."""
    age_term=0.0 if age is None else float(age)-float(age_reference)
    x=(coefficients.intercept
       + coefficients.previous_start_share*min(1.0,max(0.0,float(previous_start_share)))
       + coefficients.previous_minutes_share*min(1.0,max(0.0,float(previous_minutes_share)))
       + coefficients.fee_percentile_within_club*min(1.0,max(0.0,float(fee_percentile_within_club)))
       + coefficients.expectation_signal*min(1.0,max(0.0,float(expectation_signal)))
       + coefficients.age_centered*age_term)
    return sigmoid(x)
