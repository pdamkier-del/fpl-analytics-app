"""Human-readable, read-only PM parameter catalogue.

Every displayed value identifies its source and whether it is calibrated,
a scoring rule, a simulation default, or a runtime feature. This module never
changes simulator configuration. Unknown live values are deliberately not
filled with guessed constants.
"""
from dataclasses import asdict, dataclass
from typing import Optional

from .feature_registry import FEATURES


@dataclass(frozen=True)
class ParameterInfo:
    name: str
    module: str
    meaning: str
    kind: str
    value: Optional[str]
    unit: str
    defined_in: str
    note: str


CATALOGUE = (
    ParameterInfo("attack_goal_prior_tau", "PM / attack", "Position prior exposure for goals", "calibrated historical", "340.37043955522125", "minutes", "analysis/results/joint-component-recovery-v1/player_attack_fit.json", "Archived recovery experiment, not asserted as the value of every live forecast."),
    ParameterInfo("attack_assist_prior_tau", "PM / attack", "Position prior exposure for assists", "calibrated historical", "365.22361910394244", "minutes", "analysis/results/joint-component-recovery-v1/player_attack_fit.json", "Archived recovery experiment, not asserted as the value of every live forecast."),
    ParameterInfo("attack_goal_half_life", "PM / attack", "Recency half-life for goal estimator", "calibrated historical", "14.301700060813651", "games", "analysis/results/joint-component-recovery-v1/player_attack_fit.json", "Archived recovery experiment."),
    ParameterInfo("attack_assist_half_life", "PM / attack", "Recency half-life for assist estimator", "calibrated historical", "28.106996692019756", "games", "analysis/results/joint-component-recovery-v1/player_attack_fit.json", "Archived recovery experiment."),
    ParameterInfo("dc_threshold_DEF", "PM / DefCon", "Defender defensive contribution threshold", "FPL rule", "10", "actions", "src/fpl_v1_1_model/defcon.py", "Awards two points for reaching the threshold under 2026-27 rules."),
    ParameterInfo("dc_threshold_MID_FWD", "PM / DefCon", "Midfielder or forward defensive contribution threshold", "FPL rule", "12", "actions", "src/fpl_v1_1_model/defcon.py", "Awards two points for reaching the threshold under 2026-27 rules."),
    ParameterInfo("dc_alpha", "PM / DefCon", "NB2 overdispersion by FPL position", "runtime feature", None, "dimensionless", "src/fpl_v1_1_model/joint_simulator.py", "Historical values are position-specific; inspect the exact snapshot for live values."),
    ParameterInfo("bps_background_rate90", "PM / BPS", "Background BPS expectation per 90", "runtime feature", None, "BPS/90", "src/fpl_v1_1_model/joint_simulator.py", "Player-specific fixture input."),
    ParameterInfo("bps_background_sd90", "PM / BPS", "Background BPS standard deviation at 90 minutes", "runtime feature", None, "BPS", "src/fpl_v1_1_model/joint_simulator.py", "Historical snapshot uses position-specific values; live snapshot must be inspected."),
    ParameterInfo("bps_background_mean", "PM / BPS", "Legacy BPS fallback expectation", "fallback default", "0.0", "BPS", "src/fpl_v1_1_model/joint_simulator.py", "Read only when bps_background_rate90 is None."),
    ParameterInfo("bps_background_sd", "PM / BPS", "Legacy BPS fallback SD", "fallback default", "0.0", "BPS", "src/fpl_v1_1_model/joint_simulator.py", "Read only when bps_background_rate90 is None."),
    ParameterInfo("assist_probability_per_goal", "PM / goals", "Probability of an assist per ordinary goal", "fallback default", "0.72", "probability", "src/fpl_v1_1_model/joint_simulator.py", "May be overridden per matchup; not a universal locked calibration."),
    ParameterInfo("penalty_conversion", "PM / penalties", "Default individual penalty conversion", "fallback default", "0.78", "probability", "src/fpl_v1_1_model/joint_simulator.py", "Can be overridden per player."),
    ParameterInfo("goal_weight", "PM / attack", "Share of team goals assigned to player", "runtime feature", None, "relative weight", "src/fpl_v1_1_model/joint_simulator.py", "Computed from player data; do not treat as independently fitted constant."),
    ParameterInfo("assist_weight", "PM / attack", "Share of assists assigned to player", "runtime feature", None, "relative weight", "src/fpl_v1_1_model/joint_simulator.py", "Computed from player data; do not treat as independently fitted constant."),
    ParameterInfo("p_start", "MM / minutes", "Probability of starting", "runtime feature", None, "probability", "src/fpl_v1_1_model/joint_simulator.py", "From locked MM, not a constant."),
    ParameterInfo("start_minutes_mean", "MM / minutes", "Expected minutes conditional on starting", "runtime feature", None, "minutes", "src/fpl_v1_1_model/joint_simulator.py", "From locked MM, not a constant."),
    ParameterInfo("lambda_home_goals", "team / fixture", "Expected home goals against selected opponent", "runtime feature", None, "goals", "src/fpl_v1_1_model/joint_simulator.py", "From locked team forecast; varies by matchup."),
    ParameterInfo("lambda_away_goals", "team / fixture", "Expected away goals against selected opponent", "runtime feature", None, "goals", "src/fpl_v1_1_model/joint_simulator.py", "From locked team forecast; varies by matchup."),
)


def parameter_catalogue():
    return [asdict(p) for p in CATALOGUE]


def grouped_catalogue():
    groups = {}
    for p in parameter_catalogue():
        groups.setdefault(p["module"], []).append(p)
    return groups


def feature_and_parameter_catalogue():
    return {"features": [asdict(f) for f in FEATURES], "parameters": parameter_catalogue()}
