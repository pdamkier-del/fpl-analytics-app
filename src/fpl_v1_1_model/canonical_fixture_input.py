"""Canonical, lossless fixture boundary for the locked MM -> PM model.

This is deliberately an adapter, not a new estimator. A canonical player row
owns a single minute decomposition. The old control/v4 duplicate names are
emitted only at the existing frozen simulator boundary.
"""
import numpy as np
import pandas as pd

from .fixture_input import prepare_fixture

CANONICAL_MINUTES = (
    "p_start", "xmins", "p_cameo_given_bench",
    "start_minutes_mean", "cameo_minutes_mean",
)
LEGACY_ALIASES = {
    "control_p_start": "p_start",
    "control_xmins": "xmins",
    "v4_workload_start_p_start": "p_start",
    "v4_workload_start_xmins": "xmins",
    "v4_p_cameo_given_bench": "p_cameo_given_bench",
    "v4_start_minutes_mean": "start_minutes_mean",
    "v4_cameo_minutes_mean": "cameo_minutes_mean",
}
# These are already canonical in the existing adapter; no duplicate owner.
REQUIRED = set(CANONICAL_MINUTES) | {
    "fixture_uuid", "cutoff", "player_uuid", "team_id", "pos",
    "home_team_id", "away_team_id", "lambda_home_goals",
    "lambda_away_goals", "assist_probability_per_goal",
    "lambda_pen", "team_pen_conversion", "goal_mu", "assist_mu",
    "mu_dc", "dc_alpha", "p_yellow", "p_red", "pen_weight",
    "pen_conversion", "bg_mean_rate90", "bg_sd90", "lambda_saves",
}


def expand_canonical_fixture(frame: pd.DataFrame) -> pd.DataFrame:
    """Expand a canonical fixture without mutating data or fitting parameters.

    Reject conflicting legacy aliases and inconsistent minute identities.
    This adapter only supports cases where control and v4 minute inputs are
    identical. Different variants must use the existing explicit path.
    """
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise ValueError("Missing canonical fixture fields: " + ", ".join(sorted(missing)))
    if frame.empty:
        raise ValueError("Empty canonical fixture")
    out = frame.copy(deep=True)
    vals = out[list(CANONICAL_MINUTES)].to_numpy(dtype=float)
    if not np.isfinite(vals).all():
        raise ValueError("Nonfinite canonical minute features")
    p = out["p_start"].to_numpy(float)
    q = out["p_cameo_given_bench"].to_numpy(float)
    if ((p < 0) | (p > 1) | (q < 0) | (q > 1)).any():
        raise ValueError("Invalid canonical minute probabilities")
    duration = out[["xmins", "start_minutes_mean", "cameo_minutes_mean"]].to_numpy(float)
    if ((duration < 0) | (duration > 90)).any():
        raise ValueError("Invalid canonical minute durations")
    expected = p * out["start_minutes_mean"].to_numpy(float) + (
        (1 - p) * q * out["cameo_minutes_mean"].to_numpy(float)
    )
    if not np.allclose(expected, out["xmins"].to_numpy(float), rtol=0, atol=1e-8):
        raise ValueError("Canonical expected-minutes identity mismatch")
    for legacy, source in LEGACY_ALIASES.items():
        if legacy in out:
            candidate = out[legacy].to_numpy(float)
            if not np.isfinite(candidate).all() or not np.allclose(
                candidate, out[source].to_numpy(float), rtol=0, atol=1e-10
            ):
                raise ValueError("Conflicting legacy minute alias: " + legacy)
        out[legacy] = out[source]
    return out


def prepare_canonical_fixture(frame: pd.DataFrame, *,
                              p_keeper_save_given_miss: float,
                              bps_rules: str = "2025-26"):
    """Delegate unchanged simulation mathematics to the existing adapter."""
    return prepare_fixture(
        expand_canonical_fixture(frame),
        p_keeper_save_given_miss=p_keeper_save_given_miss,
        bps_rules=bps_rules,
    )
