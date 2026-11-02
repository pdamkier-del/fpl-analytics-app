"""Single source of truth for fixture-level feature ownership.

This is metadata and validation only: it does not estimate, impute, or modify
any of the locked MM/PM/TS calculations. Derived features keep provenance.
"""
from dataclasses import dataclass
from typing import Literal

Scope = Literal["fixture", "team", "player", "role", "derived"]


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    scope: Scope
    meaning: str
    source: str
    consumed_by: str


FEATURES = (
    FeatureDefinition("fixture_uuid", "fixture", "Stable match identity", "fixture schedule", "join"),
    FeatureDefinition("cutoff", "fixture", "Pre-deadline information boundary", "deadline", "join"),
    FeatureDefinition("home_team_id", "fixture", "Home team", "fixture schedule", "PM"),
    FeatureDefinition("away_team_id", "fixture", "Away team", "fixture schedule", "PM"),
    FeatureDefinition("lambda_home_goals", "fixture", "Expected home goals", "locked team model", "PM"),
    FeatureDefinition("lambda_away_goals", "fixture", "Expected away goals", "locked team model", "PM"),
    FeatureDefinition("assist_probability_per_goal", "fixture", "Assist incidence", "locked PM calibration", "PM"),
    FeatureDefinition("team_id", "team", "Club identity", "roster history", "join"),
    FeatureDefinition("lambda_pen", "team", "Expected team penalties", "penalty model", "PM"),
    FeatureDefinition("team_pen_conversion", "team", "Team penalty conversion", "penalty model", "PM"),
    FeatureDefinition("player_uuid", "player", "Stable player identity", "roster history", "join"),
    FeatureDefinition("pos", "player", "Official FPL scoring position", "FPL roster", "PM"),
    FeatureDefinition("p_start", "player", "Start probability", "locked MM", "MM-to-PM"),
    FeatureDefinition("p_cameo_given_bench", "player", "Bench appearance probability", "locked MM", "MM-to-PM"),
    FeatureDefinition("start_minutes_mean", "player", "Conditional starter minutes", "locked MM", "MM-to-PM"),
    FeatureDefinition("cameo_minutes_mean", "player", "Conditional cameo minutes", "locked MM", "MM-to-PM"),
    FeatureDefinition("xmins", "derived", "Expected minutes identity", "locked MM", "MM-to-PM"),
    FeatureDefinition("goal_mu", "derived", "Team-normalized player goal propensity", "locked attack adapter", "PM"),
    FeatureDefinition("assist_mu", "derived", "Team-normalized player assist propensity", "locked attack adapter", "PM"),
    FeatureDefinition("mu_dc", "derived", "Player defensive contribution rate", "locked DC estimator", "PM"),
    FeatureDefinition("dc_alpha", "derived", "DefCon dispersion", "position calibration", "PM"),
    FeatureDefinition("p_yellow", "derived", "Yellow card probability", "discipline estimator", "PM"),
    FeatureDefinition("p_red", "derived", "Red card probability", "discipline estimator", "PM"),
    FeatureDefinition("pen_weight", "derived", "Penalty taker weight", "penalty model", "PM"),
    FeatureDefinition("pen_conversion", "derived", "Player penalty conversion", "penalty model", "PM"),
    FeatureDefinition("bg_mean_rate90", "derived", "BPS background mean per 90", "BPS estimator", "PM"),
    FeatureDefinition("bg_sd90", "derived", "BPS background dispersion per 90", "BPS estimator", "PM"),
    FeatureDefinition("lambda_saves", "derived", "Goalkeeper save intensity", "keeper estimator", "PM"),
    FeatureDefinition("q_role_slow", "role", "Pre-deadline tactical role distribution (multi-column q_*)", "role history", "prior estimator"),
)

def owner_map():
    """Feature -> owner, rejecting duplicated ownership."""
    result = {}
    for item in FEATURES:
        if item.name in result:
            raise ValueError("Duplicate feature owner: " + item.name)
        result[item.name] = item.scope
    return result

def feature_catalogue():
    """Serializable data dictionary for audit or documentation."""
    from dataclasses import asdict
    return [asdict(item) for item in FEATURES]
