"""Goalkeeper shot-on-target and save model for FPL v1.1.

Phase 3G uses Football-Data team SOT as an external *predictor definition*.
Because provider SOT matches FPL saves + goals only ~84% of historical team
sides, it is not forced to be an algebraic truth.  The model therefore has two
layers:

1. opponent SOT creation + defending-team SOT allowed -> source-SOT mean;
2. source-SOT mean -> expected FPL-counted saves.

The existing team-goal model supplies the goal mean.  Monte Carlo then draws
FPL goals and saves coherently and defines modelled SOT as their sum.  This
keeps exact FPL scoring without pretending two providers share identical event
definitions.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Any


@dataclass(frozen=True)
class SOTRateParams:
    opponent_weight: float
    intercept: float
    attacker_home_log_effect: float
    attack_half_life: float = 13.0
    defence_half_life: float = 20.0
    min_history_matches: int = 5

    def __post_init__(self) -> None:
        if not 0.0 <= self.opponent_weight <= 1.0:
            raise ValueError("opponent_weight must be in [0,1]")
        if self.attack_half_life <= 0 or self.defence_half_life <= 0:
            raise ValueError("half-lives must be positive")
        if self.min_history_matches < 1:
            raise ValueError("min_history_matches must be positive")


@dataclass(frozen=True)
class SaveRateParams:
    intercept: float
    sot_exponent: float
    attacker_home_log_effect: float
    distribution: str = "poisson"

    def __post_init__(self) -> None:
        if self.sot_exponent <= 0:
            raise ValueError("sot_exponent must be positive")
        if self.distribution != "poisson":
            raise ValueError("Phase 3G selected Poisson saves")


@dataclass(frozen=True)
class KeeperShotModel:
    """Backward-compatible total-SOT thinning representation."""
    lambda_sot_faced: float
    lambda_goals_conceded: float

    def __post_init__(self) -> None:
        if self.lambda_sot_faced < 0 or self.lambda_goals_conceded < 0:
            raise ValueError("keeper means must be non-negative")
        if self.lambda_goals_conceded > self.lambda_sot_faced + 1e-12:
            raise ValueError("expected goals conceded cannot exceed expected SOT faced")

    @property
    def lambda_saves(self) -> float:
        return self.lambda_sot_faced - self.lambda_goals_conceded

    @property
    def shot_conversion_probability(self) -> float:
        if self.lambda_sot_faced <= 0:
            return 0.0
        return self.lambda_goals_conceded / self.lambda_sot_faced


@dataclass(frozen=True)
class KeeperEventModel:
    """FPL event means used by the joint match simulation."""
    lambda_goals_conceded: float
    lambda_saves: float

    def __post_init__(self) -> None:
        if self.lambda_goals_conceded < 0 or self.lambda_saves < 0:
            raise ValueError("keeper event means must be non-negative")

    @property
    def lambda_sot_faced(self) -> float:
        return self.lambda_goals_conceded + self.lambda_saves


@dataclass(frozen=True)
class KeeperShotOutcome:
    shots_on_target_faced: int
    goals_conceded: int
    saves: int

    def __post_init__(self) -> None:
        if min(self.shots_on_target_faced, self.goals_conceded, self.saves) < 0:
            raise ValueError("keeper outcome counts must be non-negative")
        if self.goals_conceded + self.saves != self.shots_on_target_faced:
            raise ValueError("SOT faced must equal goals conceded + saves")


def blend_sot_rate(
    opponent_sot_for: float,
    team_sot_against: float,
    league_sot_per_team_match: float,
    *,
    opponent_weight: float = 0.5,
) -> float:
    """Auditable arithmetic blend of opponent creation and team allowance."""
    vals = (opponent_sot_for, team_sot_against, league_sot_per_team_match)
    if any(float(v) < 0 for v in vals):
        raise ValueError("SOT rates must be non-negative")
    w = float(opponent_weight)
    if not 0.0 <= w <= 1.0:
        raise ValueError("opponent_weight must be in [0,1]")
    a = float(opponent_sot_for)
    b = float(team_sot_against)
    if a == 0 and b == 0:
        return float(league_sot_per_team_match)
    if a == 0:
        return b
    if b == 0:
        return a
    return w * a + (1.0 - w) * b


def forecast_source_sot_mean(
    opponent_sot_for: float,
    team_sot_against: float,
    league_sot_per_team_match: float,
    *,
    attacker_was_home: bool,
    params: SOTRateParams,
) -> float:
    """Forecast Football-Data-definition SOT for the attacking side."""
    base = blend_sot_rate(
        opponent_sot_for, team_sot_against, league_sot_per_team_match,
        opponent_weight=params.opponent_weight,
    )
    return max(0.0, exp(params.intercept + params.attacker_home_log_effect * int(bool(attacker_was_home))) * base)


def forecast_fpl_save_mean(source_sot_mean: float, *, attacker_was_home: bool, params: SaveRateParams) -> float:
    """Map source-SOT opportunity to expected FPL-counted goalkeeper saves."""
    x = float(source_sot_mean)
    if x < 0:
        raise ValueError("source_sot_mean must be non-negative")
    if x == 0:
        return 0.0
    return exp(params.intercept + params.attacker_home_log_effect * int(bool(attacker_was_home))) * x ** params.sot_exponent


def coherent_shot_model(lambda_sot_faced: float, lambda_goals_conceded: float) -> KeeperShotModel:
    """Construct the original thinning representation."""
    return KeeperShotModel(float(lambda_sot_faced), float(lambda_goals_conceded))


def coherent_event_model(lambda_goals_conceded: float, lambda_saves: float) -> KeeperEventModel:
    """Construct the Phase 3G goal + FPL-save representation."""
    return KeeperEventModel(float(lambda_goals_conceded), float(lambda_saves))


def sample_keeper_shots(rng: Any, model: KeeperShotModel) -> KeeperShotOutcome:
    """Draw the backward-compatible Poisson-thinning keeper outcome."""
    n_sot = int(rng.poisson(model.lambda_sot_faced))
    if n_sot <= 0:
        return KeeperShotOutcome(0, 0, 0)
    goals = int(rng.binomial(n_sot, model.shot_conversion_probability))
    return KeeperShotOutcome(n_sot, goals, n_sot - goals)


def sample_keeper_events(rng: Any, model: KeeperEventModel) -> KeeperShotOutcome:
    """Draw goals and FPL saves, then define coherent modelled SOT as their sum.

    Independent Poisson goals/saves is equivalent to Poisson thinning when the
    total mean is their sum, while allowing source-SOT to be calibrated to the
    FPL save definition rather than forced to equal it.
    """
    goals = int(rng.poisson(model.lambda_goals_conceded))
    saves = int(rng.poisson(model.lambda_saves))
    return KeeperShotOutcome(goals + saves, goals, saves)


def save_points(saves: int) -> int:
    """Official FPL save bucket: one point for every three saves."""
    s = int(saves)
    if s < 0:
        raise ValueError("saves must be non-negative")
    return s // 3


def goals_conceded_deduction(goals_conceded: int) -> int:
    """Official GK deduction: -1 for every two goals conceded."""
    g = int(goals_conceded)
    if g < 0:
        raise ValueError("goals_conceded must be non-negative")
    return -(g // 2)


def keeper_event_points(*, saves: int, goals_conceded: int, penalty_saves: int = 0) -> int:
    """Keeper-specific event points excluding appearance/CS/goals/assists/bonus."""
    p = int(penalty_saves)
    if p < 0:
        raise ValueError("penalty_saves must be non-negative")
    return save_points(saves) + goals_conceded_deduction(goals_conceded) + 5 * p


def expected_save_points_poisson(lambda_saves: float, tol: float = 1e-12) -> float:
    """Exact E[floor(S/3)] for S~Poisson(lambda_saves), for diagnostics."""
    lam = float(lambda_saves)
    if lam < 0:
        raise ValueError("lambda_saves must be non-negative")
    if lam == 0:
        return 0.0
    p = exp(-lam)
    cumulative = p
    total = 0.0
    n = 0
    while n < 300 and 1.0 - cumulative > tol:
        n += 1
        p *= lam / n
        cumulative += p
        total += (n // 3) * p
    return total


def expected_gc_deduction_poisson(lambda_goals: float, tol: float = 1e-12) -> float:
    """Exact E[-floor(G/2)] for G~Poisson(lambda_goals), for diagnostics."""
    lam = float(lambda_goals)
    if lam < 0:
        raise ValueError("lambda_goals must be non-negative")
    if lam == 0:
        return 0.0
    p = exp(-lam)
    cumulative = p
    total = 0.0
    n = 0
    while n < 300 and 1.0 - cumulative > tol:
        n += 1
        p *= lam / n
        cumulative += p
        total += -(n // 2) * p
    return total
