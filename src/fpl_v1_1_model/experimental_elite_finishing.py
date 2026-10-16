"""Offline, opt-in long-history finishing sensitivity for player PM v2.

This does not claim an identified non-penalty skill, a top-player bonus,
or a new production forecast. It replaces (never stacks) the existing
player finishing factor inside the existing on-pitch PM v2 law.
"""
from copy import deepcopy
from dataclasses import replace
import numpy as np
import pandas as pd


def finishing_estimates(history, cutoff, player_ids, *, half_life_days=730.,
                        prior_xg=20., cap=(0.75, 1.25),
                        goals_column="goals", xg_column="xg"):
    """Deadline-only Gamma/Poisson posterior means, neutral prior 1.

    All-xG and credited goals are an effective conversion calibration.
    Separate non-penalty skill is only identified with same-provider,
    time-valid non-penalty xG and non-penalty goal columns.
    """
    if not np.isfinite([half_life_days, prior_xg, *cap]).all():
        raise ValueError("Non-finite parameters")
    if half_life_days <= 0 or prior_xg <= 0 or not 0 < cap[0] <= 1 <= cap[1]:
        raise ValueError("Invalid shrinkage or cap")
    required = {"player_uuid", "known", goals_column, xg_column}
    if not required.issubset(history.columns):
        raise ValueError("Missing historical finishing evidence")
    h = history[list(required)].copy()
    h["known"] = pd.to_datetime(h.known, utc=True)
    cut = pd.Timestamp(cutoff)
    if cut.tzinfo is None:
        raise ValueError("Cutoff must be timezone-aware")
    cut = cut.tz_convert("UTC")
    h = h[h.known.notna() & (h.known < cut)]
    if h[[goals_column, xg_column]].isna().any().any():
        raise ValueError("Missing evidence before cutoff; no zero fill")
    y = h[goals_column].to_numpy(dtype=float)
    x = h[xg_column].to_numpy(dtype=float)
    if not np.isfinite(y).all() or not np.isfinite(x).all() or (y < 0).any() or (x < 0).any():
        raise ValueError("Invalid counts or xG")
    age = (cut - h.known).dt.total_seconds().to_numpy() / 86400
    h["_w"] = np.exp2(-age / half_life_days)
    h["_g"] = y * h["_w"].to_numpy()
    h["_x"] = x * h["_w"].to_numpy()
    totals = h.groupby("player_uuid")[["_g", "_x"]].sum()
    result = {}
    for pid in player_ids:
        key = str(pid)
        # Historical UUIDs and forecast player IDs share canonical strings.
        matches = totals.loc[totals.index.astype(str) == key]
        g = float(matches["_g"].sum())
        exposure = float(matches["_x"].sum())
        raw = (g + prior_xg) / (exposure + prior_xg)
        result[pid] = dict(
            factor=float(np.clip(raw, *cap)),
            raw_factor=float(raw),
            weighted_goals=g,
            weighted_xg=exposure,
            prior_xg=float(prior_xg),
            history_type=f"{goals_column}/{xg_column}",
        )
    return result


def with_finishing_candidate(inp, spec, estimates):
    """Apply a replacement finishing profile only to experimental PM v2.

    Original goal_weight was built with old theta. Replace theta once.
    The team ordinary-goal adjustment remains solely in lineup_rates;
    no independent team lambda or penalty adjustment is made.
    """
    if not spec.get("finishing"):
        raise ValueError("Requires existing finishing-enabled PM v2")
    updated = deepcopy(spec)
    players = []
    for p in inp.players:
        if p.player_id not in updated["profiles"] or p.player_id not in estimates:
            raise ValueError("Incomplete player profiles")
        profile = updated["profiles"][p.player_id]
        old = float(profile["finishing"]["mean"])
        new = float(estimates[p.player_id]["factor"])
        if not np.isfinite([old, new]).all() or old <= 0 or new <= 0:
            raise ValueError("Invalid replacement finishing factor")
        profile["finishing"] = dict(profile["finishing"], mean=new)
        players.append(replace(p, goal_weight=p.goal_weight * (new / old)))
    return replace(inp, players=tuple(players)), updated
