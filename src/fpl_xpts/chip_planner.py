from __future__ import annotations

"""Simple rolling FPL chip planner.

The locked MM/PM/TS models are inputs only. This module does not alter them.

Core rule:
  raw_EV(c,i,g+k) = expected marginal FPL points from using the chip
  adjusted_EV(c,i,g+k) = raw_EV * certainty * future_discount**k

At each decision GW, compare the best immediate raw EV with the best discounted
future option value. Only the current GW action is executed; values are
recomputed next GW from fresh forecasts.

Raw chip EV definitions:
- TC: extra third captain score, approximately player xP for that GW.
      All top forecast players are evaluated, not just the current squad.
- BB: sum of xP of the four bench players under the BB squad/lineup plan.
- FH: optimal one-GW Free Hit squad xP minus normal no-FH squad xP.
- WC: weighted future utility of optimal wildcard squad minus normal TS path.

Only one chip can be used in a GW. Near the chip-period deadline, if the number
of remaining GWs is no larger than the number of remaining chips, the planner
forces a use-now decision so a chip does not expire unused.
"""

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

CHIPS = ("TC", "BB", "FH", "WC")


@dataclass(frozen=True)
class ChipPlannerConfig:
    """Chip-only decision parameters.

    future_discount is deliberately separate from TS rho=.60. TS rho values
    transfer utility over a 6GW planning path; this factor expresses confidence
    decay in future chip opportunities and defaults to a mild 3% per GW.
    """

    future_discount: float = 0.97
    top_tc_candidates: int = 20
    min_use_edge: float = 0.0

    def __post_init__(self) -> None:
        if not (0.0 < self.future_discount <= 1.0):
            raise ValueError("future_discount must be in (0,1]")
        if self.top_tc_candidates < 1:
            raise ValueError("top_tc_candidates must be >= 1")


def build_tc_values(
    forecast: pd.DataFrame,
    *,
    current_gw: int,
    period_end_gw: int,
    config: ChipPlannerConfig = ChipPlannerConfig(),
    id_col: str = "id",
    gw_col: str = "gw",
    xp_col: str = "xpts_mean",
    certainty_col: str | None = None,
    name_col: str | None = "web_name",
) -> pd.DataFrame:
    """Evaluate TC over all top forecast players in every reachable GW."""

    req = {id_col, gw_col, xp_col}
    missing = req.difference(forecast.columns)
    if missing:
        raise ValueError(f"forecast missing columns: {sorted(missing)}")

    f = forecast.copy()
    f[gw_col] = pd.to_numeric(f[gw_col], errors="coerce")
    f[xp_col] = pd.to_numeric(f[xp_col], errors="coerce")
    f = f[f[gw_col].between(current_gw, period_end_gw) & f[xp_col].notna()].copy()

    if f.empty:
        return pd.DataFrame(columns=[
            "chip","gw","candidate_id","candidate_name","raw_value","certainty"
        ])

    parts = []
    for gw, g in f.groupby(gw_col, sort=True):
        g = g.sort_values(xp_col, ascending=False).head(config.top_tc_candidates).copy()
        out = pd.DataFrame({
            "chip": "TC",
            "gw": int(gw),
            "candidate_id": g[id_col].to_numpy(),
            "candidate_name": (
                g[name_col].astype(str).to_numpy()
                if name_col is not None and name_col in g.columns
                else g[id_col].astype(str).to_numpy()
            ),
            "raw_value": g[xp_col].to_numpy(float),
            "certainty": (
                pd.to_numeric(g[certainty_col], errors="coerce").fillna(1.0).clip(0,1).to_numpy(float)
                if certainty_col is not None and certainty_col in g.columns
                else np.ones(len(g), dtype=float)
            ),
        })
        parts.append(out)
    return pd.concat(parts, ignore_index=True)


def normalize_chip_values(values: pd.DataFrame) -> pd.DataFrame:
    """Validate generic chip-value rows."""
    req = {'chip','gw','raw_value'}
    missing = req.difference(values.columns)
    if missing:
        raise ValueError(f"chip values missing columns: {sorted(missing)}")
    x = values.copy()
    x["chip"] = x["chip"].astype(str).str.upper()
    bad = sorted(set(x["chip"]) - set(CHIPS))
    if bad:
        raise ValueError(f"unknown chips: {bad}")
    x["gw"] = pd.to_numeric(x["gw"], errors="raise").astype(int)
    x["raw_value"] = pd.to_numeric(x["raw_value"], errors="raise").astype(float)
    if "certainty" not in x:
        x["certainty"] = 1.0
    x["certainty"] = pd.to_numeric(x["certainty"], errors="coerce").fillna(1.0).clip(0,1)
    if "candidate_id" not in x:
        x["candidate_id"] = ""
    if "candidate_name" not in x:
        x["candidate_name"] = x["candidate_id"].astype(str)
    return x


def best_chip_options(values: pd.DataFrame, *, current_gw: int, period_end_gw: int,
                      config: ChipPlannerConfig = ChipPlannerConfig()) -> pd.DataFrame:
    """Return the best candidate for each chip x GW after uncertainty discount."""
    x = normalize_chip_values(values)
    x = x[x.gw.between(current_gw, period_end_gw)].copy()
    if x.empty:
        x["gw_offset"] = pd.Series(dtype=int)
        x["adjusted_value"] = pd.Series(dtype=float)
        return x
    x["gw_offset"] = x.gw - int(current_gw)
    x["adjusted_value"] = x.raw_value * x.certainty * np.power(config.future_discount, x.gw_offset)
    idx = x.groupby(["chip","gw"], sort=True)["adjusted_value"].idxmax()
    return x.loc[idx].sort_values(["chip","gw"]).reset_index(drop=True)


def decide_chip(values: pd.DataFrame, *, current_gw: int, period_end_gw: int,
                chips_remaining: Iterable[str],
                config: ChipPlannerConfig = ChipPlannerConfig()) -> dict:
    """Choose NONE or one chip for the current GW."""
    remaining = tuple(dict.fromkeys(str(c).upper() for c in chips_remaining))
    bad = sorted(set(remaining) - set(CHIPS))
    if bad:
        raise ValueError(f"unknown chips_remaining: {bad}")

    opts = best_chip_options(values, current_gw=current_gw, period_end_gw=period_end_gw, config=config)
    opts = opts[opts.chip.isin(remaining)].copy()
    rows = []
    for chip in remaining:
        c = opts[opts.chip.eq(chip)]
        now = c[c.gw.eq(current_gw)]
        future = c[c.gw.gt(current_gw)]
        if len(now):
            nr = now.loc[now.raw_value.idxmax()]
            now_value = float(nr.raw_value)
            now_candidate_id = nr.candidate_id
            now_candidate_name = nr.candidate_name
            now_certainty = float(nr.certainty)
        else:
            now_value = float("-inf")
            now_candidate_id = ""
            now_candidate_name = ""
            now_certainty = 0.0
        if len(future):
            fr = future.loc[future.adjusted_value.idxmax()]
            future_value = float(fr.adjusted_value)
            future_gw = int(fr.gw)
            future_candidate_id = fr.candidate_id
            future_candidate_name = fr.candidate_name
        else:
            future_value = 0.0
            future_gw = None
            future_candidate_id = ""
            future_candidate_name = ""
        rows.append(dict(
            chip=chip,
            use_now_value=now_value,
            now_candidate_id=now_candidate_id,
            now_candidate_name=now_candidate_name,
            now_certainty=now_certainty,
            save_option_value=future_value,
            best_future_gw=future_gw,
            best_future_candidate_id=future_candidate_id,
            best_future_candidate_name=future_candidate_name,
            use_edge=now_value-future_value,
        ))

    comparison = pd.DataFrame(rows)
    remaining_gws = int(period_end_gw-current_gw+1)
    forced = len(remaining)>0 and remaining_gws<=len(remaining)
    viable = comparison[np.isfinite(comparison.use_now_value)].copy()
    if viable.empty:
        return {"action":"NONE","chip":None,"candidate_id":None,"candidate_name":None,
                "forced_by_expiry":forced,"comparison":comparison}
    if forced:
        choice = viable.loc[viable.use_now_value.idxmax()]
        reason = "expiry_pressure"
    else:
        profitable = viable[viable.use_edge>config.min_use_edge]
        if profitable.empty:
            return {"action":"NONE","chip":None,"candidate_id":None,"candidate_name":None,
                    "forced_by_expiry":False,"comparison":comparison}
        choice = profitable.loc[profitable.use_edge.idxmax()]
        reason = "use_now_beats_future_option"
    return {
        "action":"USE",
        "chip":str(choice.chip),
        "candidate_id":choice.now_candidate_id,
        "candidate_name":choice.now_candidate_name,
        "raw_value":float(choice.use_now_value),
        "save_option_value":float(choice.save_option_value),
        "use_edge":float(choice.use_edge),
        "forced_by_expiry":forced,
        "reason":reason,
        "comparison":comparison,
    }

def tc_opportunity_probabilities(
    samples: pd.DataFrame,
    *,
    current_gw: int,
    period_end_gw: int,
    config: ChipPlannerConfig = ChipPlannerConfig(),
    sim_col: str = "simulation",
    gw_col: str = "gw",
    points_col: str = "points",
    id_col: str = "candidate_id",
    name_col: str = "candidate_name",
) -> pd.DataFrame:
    """Probability that each remaining GW is the best TC opportunity."""
    req = {sim_col, gw_col, points_col, id_col}
    missing = req.difference(samples.columns)
    if missing:
        raise ValueError(f"TC samples missing columns: {sorted(missing)}")
    x = samples.copy()
    x[gw_col] = pd.to_numeric(x[gw_col], errors="raise").astype(int)
    x[points_col] = pd.to_numeric(x[points_col], errors="raise").astype(float)
    x = x[x[gw_col].between(current_gw, period_end_gw)].copy()
    if x.empty:
        raise ValueError("No TC samples in requested GW range")
    if name_col not in x:
        x[name_col] = x[id_col].astype(str)

    idx = x.groupby([sim_col, gw_col], sort=True)[points_col].idxmax()
    best = x.loc[idx, [sim_col, gw_col, id_col, name_col, points_col]].copy()
    best["gw_offset"] = best[gw_col] - int(current_gw)
    best["reliability"] = np.power(config.future_discount, best.gw_offset)
    best["adjusted_points"] = best[points_col] * best.reliability

    best = best.sort_values([sim_col, "adjusted_points", gw_col], ascending=[True, False, True])
    winners = best.groupby(sim_col, sort=False).head(1)
    n_sim = int(best[sim_col].nunique())
    if n_sim <= 0:
        raise ValueError("No simulations")
    counts = winners[gw_col].value_counts().to_dict()

    rows = []
    for gw in range(int(current_gw), int(period_end_gw)+1):
        g = best[best[gw_col].eq(gw)]
        if len(g):
            mean_best = float(g.groupby(sim_col)[points_col].max().mean())
            mean_adjusted = float(g.groupby(sim_col)["adjusted_points"].max().mean())
        else:
            mean_best = float("nan")
            mean_adjusted = float("nan")
        rows.append(dict(
            gw=gw,
            probability_best=float(counts.get(gw,0)/n_sim),
            expected_best_tc_points=mean_best,
            expected_adjusted_tc_points=mean_adjusted,
            reliability=float(config.future_discount ** (gw-current_gw)),
        ))
    out = pd.DataFrame(rows)
    total = float(out.probability_best.sum())
    if not np.isclose(total,1.0,atol=1e-12):
        raise RuntimeError(f"TC GW probabilities do not sum to one: {total}")
    return out


def decide_tc_from_samples(
    samples: pd.DataFrame,
    *,
    current_gw: int,
    period_end_gw: int,
    config: ChipPlannerConfig = ChipPlannerConfig(),
    sim_col: str = "simulation",
    gw_col: str = "gw",
    points_col: str = "points",
    id_col: str = "candidate_id",
    name_col: str = "candidate_name",
) -> dict:
    """Expected-value TC stopping rule plus normalized timing probabilities."""
    probs = tc_opportunity_probabilities(
        samples,current_gw=current_gw,period_end_gw=period_end_gw,config=config,
        sim_col=sim_col,gw_col=gw_col,points_col=points_col,id_col=id_col,name_col=name_col,
    )
    x = samples.copy()
    x[gw_col] = pd.to_numeric(x[gw_col], errors="raise").astype(int)
    x[points_col] = pd.to_numeric(x[points_col], errors="raise").astype(float)
    x = x[x[gw_col].between(current_gw,period_end_gw)].copy()
    if name_col not in x:
        x[name_col] = x[id_col].astype(str)
    idx = x.groupby([sim_col,gw_col],sort=True)[points_col].idxmax()
    best = x.loc[idx,[sim_col,gw_col,id_col,name_col,points_col]].copy()
    best["adjusted_points"] = best[points_col] * np.power(config.future_discount,best[gw_col]-int(current_gw))
    now = best[best[gw_col].eq(current_gw)]
    if now.empty:
        raise ValueError(f"No TC candidates for current GW{current_gw}")
    use_now = float(now.groupby(sim_col)[points_col].max().mean())
    future = best[best[gw_col].gt(current_gw)]
    save_value = 0.0 if future.empty else float(future.groupby(sim_col).adjusted_points.max().mean())
    cur_player = (
        x[x[gw_col].eq(current_gw)]
        .groupby([id_col,name_col],as_index=False)[points_col].mean()
        .sort_values(points_col,ascending=False)
        .iloc[0]
    )
    use = (current_gw==period_end_gw) or (use_now >= save_value + config.min_use_edge)
    return dict(
        action="USE_TC" if use else "SAVE_TC",
        current_gw=int(current_gw),
        period_end_gw=int(period_end_gw),
        candidate_id=cur_player[id_col] if use else None,
        candidate_name=cur_player[name_col] if use else None,
        use_now_value=use_now,
        save_option_value=save_value,
        use_edge=use_now-save_value,
        probability_current_gw_best=float(probs.loc[probs.gw.eq(current_gw),"probability_best"].iloc[0]),
        timing_probabilities=probs,
    )