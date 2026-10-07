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

# Four-season (2022/23--2025/26) historical pre-GW calibration.
# This is a structural prior for an as-yet-unresolved future DGW opportunity,
# not a forecast for any named player or gameweek.
DEFAULT_TC_DGW_REFERENCE_XP = 12.26875

# Four-season structural prior: probability that at least one DGW still remains
# later in the active chip half. This is intentionally anonymous: it says
# "a DGW opportunity is still likely to emerge", not which team/GW will double.
STRUCTURAL_DGW_PRIOR_BY_GW = {
    **{gw:0.75 for gw in range(1,7)},
    **{gw:0.50 for gw in range(7,9)},
    **{gw:0.25 for gw in range(9,19)},
    19:0.0,
    **{gw:1.00 for gw in range(20,33)},
    **{gw:0.75 for gw in range(33,36)},
    36:0.50,
    37:0.0,
    38:0.0,
}


def structural_dgw_probability(current_gw: int) -> float:
    """Historical probability that an unresolved later DGW remains in the half."""
    gw=int(current_gw)
    if gw not in STRUCTURAL_DGW_PRIOR_BY_GW:
        raise ValueError("current_gw must be 1..38")
    return float(STRUCTURAL_DGW_PRIOR_BY_GW[gw])



def probabilistic_dgw_xp(base_gw_xp: float, extra_fixture_xp: float, concrete_probability: float) -> float:
    """Expected GW xP when an extra fixture may land in this GW.

    A confirmed DGW has probability=1 and therefore becomes an ordinary
    two-fixture GW forecast. A merely possible DGW contributes only its
    probability-weighted extra-fixture xP.
    """
    p=float(concrete_probability)
    if not 0.0 <= p <= 1.0:
        raise ValueError("concrete_probability must be in [0,1]")
    return float(base_gw_xp) + p*float(extra_fixture_xp)


def unresolved_dgw_probability(structural_probability: float, concrete_probability: float) -> float:
    """Residual probability mass for an unidentified future DGW.

    As a concrete DGW scenario becomes identified, probability mass transfers
    out of the latent option. At concrete_probability=1 the latent option is
    fully resolved and disappears.
    """
    ps=float(structural_probability);pc=float(concrete_probability)
    if not 0.0 <= ps <= 1.0:
        raise ValueError("structural_probability must be in [0,1]")
    if not 0.0 <= pc <= 1.0:
        raise ValueError("concrete_probability must be in [0,1]")
    return float(ps*(1.0-pc))


unresolved_dgw_probability_fn = unresolved_dgw_probability


def latent_dgw_option_value(
    *,
    mu_tc: float,
    unresolved_probability: float,
    dgw_reference_xp: float = DEFAULT_TC_DGW_REFERENCE_XP,
) -> float | None:
    """Absolute TC option value of an unidentified future DGW.

    Returns None once no unresolved DGW probability remains, so the latent
    option cannot double-count a concrete/confirmed DGW. Otherwise the option
    is a probability-weighted regression from the normal TC baseline toward
    the historical DGW opportunity level.
    """
    p=float(unresolved_probability)
    if not 0.0 <= p <= 1.0:
        raise ValueError("unresolved_probability must be in [0,1]")
    if p <= 0.0:
        return None
    mu=float(mu_tc);ref=float(dgw_reference_xp)
    return float(mu + p*(max(ref,mu)-mu))



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

@dataclass(frozen=True)
class TCV2Config:
    """Empirically calibrated TC-v2 timing/candidate policy."""

    mu_tc: float = 8.57
    q75_tolerance: float = 0.50
    dgw_reference_xp: float = DEFAULT_TC_DGW_REFERENCE_XP
    reliability_curve: tuple[float, ...] = (
        1.0,0.7572751521131194,0.7032843858581395,0.7047189482895067,
        0.7294450774664305,0.6880248132392998,0.6620089774056516,
        0.6816599534494022,0.7101325898781952,0.6529360545248581,
        0.7087400991235955,0.6672920340616874,0.6971400904834832,
        0.5674284775030258,0.5791542145584311,0.745201742667648,
        0.6785355419273525,0.8894051176011658,
    )

    def reliability(self, k: int) -> float:
        if k <= 0:
            return 1.0
        if k < len(self.reliability_curve):
            return float(self.reliability_curve[k])
        return float(np.nanmedian(self.reliability_curve[5:13]))


def _tc_v2_candidates(
    samples: pd.DataFrame,
    *,
    gw_col: str,
    points_col: str,
    id_col: str,
    name_col: str,
    q75_tolerance: float,
) -> pd.DataFrame:
    grp=samples.groupby([gw_col,id_col,name_col],sort=False)[points_col]
    s=grp.agg(mean="mean").reset_index()
    s=s.merge(
        grp.quantile(.75).rename("q75").reset_index(),
        on=[gw_col,id_col,name_col],how="left"
    )
    rows=[]
    for gw,g in s.groupby(gw_col,sort=True):
        maxmean=float(g["mean"].max())
        eligible=g[g["mean"]>=maxmean-float(q75_tolerance)].copy()
        rows.append(eligible.sort_values(["q75","mean"],ascending=False).iloc[0])
    return pd.DataFrame(rows).sort_values(gw_col).reset_index(drop=True)


def decide_tc_v2_from_samples(
    samples: pd.DataFrame,
    *,
    current_gw: int,
    period_end_gw: int,
    unresolved_dgw_probability: float | None = None,
    concrete_dgw_probability: float = 0.0,
    config: TCV2Config = TCV2Config(),
    gw_col: str = "gw",
    points_col: str = "points",
    id_col: str = "candidate_id",
    name_col: str = "candidate_name",
) -> dict:
    """TC-v2 decision including an unresolved future-DGW option.

    Concrete/probabilistic DGW fixtures belong in the ordinary per-GW samples.
    This function adds only the residual *unidentified* DGW option, preventing
    double counting as schedule information resolves.
    """
    req={gw_col,points_col,id_col}
    missing=req.difference(samples.columns)
    if missing:
        raise ValueError(f"TC samples missing columns: {sorted(missing)}")
    x=samples.copy()
    x[gw_col]=pd.to_numeric(x[gw_col],errors="raise").astype(int)
    x[points_col]=pd.to_numeric(x[points_col],errors="raise").astype(float)
    x=x[x[gw_col].between(current_gw,period_end_gw)].copy()
    if x.empty:
        raise ValueError("No TC samples in requested GW range")
    if name_col not in x:
        x[name_col]=x[id_col].astype(str)

    chosen=_tc_v2_candidates(
        x,gw_col=gw_col,points_col=points_col,id_col=id_col,name_col=name_col,
        q75_tolerance=config.q75_tolerance,
    )
    cur=chosen[chosen[gw_col].eq(current_gw)]
    if cur.empty:
        raise ValueError(f"No TC candidate for current GW{current_gw}")
    cr=cur.iloc[0]
    use_now=float(cr["mean"])

    future=chosen[chosen[gw_col].gt(current_gw)].copy()
    if len(future):
        future["adjusted_value"]=[
            float(config.mu_tc + config.reliability(int(g-current_gw))*(m-config.mu_tc))
            for g,m in zip(future[gw_col],future["mean"])
        ]
        fr=future.loc[future.adjusted_value.idxmax()]
        concrete_save=float(fr.adjusted_value)
        best_future_gw=int(fr[gw_col])
        best_future_candidate_name=str(fr[name_col])
    else:
        concrete_save=0.0;best_future_gw=None;best_future_candidate_name=None

    if unresolved_dgw_probability is None:
        structural=structural_dgw_probability(current_gw)
        unresolved=float(unresolved_dgw_probability_fn(structural,concrete_dgw_probability))
    else:
        unresolved=float(unresolved_dgw_probability)
        structural=None
    latent=latent_dgw_option_value(
        mu_tc=config.mu_tc,
        unresolved_probability=unresolved,
        dgw_reference_xp=config.dgw_reference_xp,
    )
    latent_save=0.0 if latent is None else float(latent)
    save_value=max(concrete_save,latent_save)
    save_source="latent_dgw" if latent is not None and latent_save>concrete_save else "concrete_gw"
    use=(current_gw==period_end_gw) or (use_now>=save_value)

    return dict(
        action="USE_TC" if use else "SAVE_TC",
        current_gw=int(current_gw),
        period_end_gw=int(period_end_gw),
        candidate_id=cr[id_col] if use else None,
        candidate_name=cr[name_col] if use else None,
        use_now_value=use_now,
        concrete_save_option_value=concrete_save,
        latent_dgw_option_value=(None if latent is None else float(latent)),
        unresolved_dgw_probability=unresolved,
        structural_dgw_probability=structural,
        concrete_dgw_probability=float(concrete_dgw_probability),
        save_option_value=save_value,
        save_source=save_source,
        best_future_gw=best_future_gw,
        best_future_candidate_name=best_future_candidate_name,
        use_edge=use_now-save_value,
    )



def fh_opportunity_probabilities(
    samples: pd.DataFrame,
    *,
    current_gw: int,
    period_end_gw: int,
    config: ChipPlannerConfig = ChipPlannerConfig(),
    sim_col: str = "simulation",
    gw_col: str = "gw",
    points_col: str = "points",
) -> pd.DataFrame:
    """Probability that each remaining GW is the best Free Hit opportunity.

    points must already be the ex-ante FH marginal value for that simulation:
        optimal FH XI + captain - normal TS XI + captain
    The normal path may include the transfers/hits TS would actually choose.

    Free Hit changes no persistent squad state. The same uncertainty discount
    used by the TC stopping rule is applied to future FH opportunities.
    """
    req={sim_col,gw_col,points_col}
    missing=req.difference(samples.columns)
    if missing:
        raise ValueError(f"FH samples missing columns: {sorted(missing)}")
    x=samples.copy()
    x[gw_col]=pd.to_numeric(x[gw_col],errors="raise").astype(int)
    x[points_col]=pd.to_numeric(x[points_col],errors="raise").astype(float)
    x=x[x[gw_col].between(current_gw,period_end_gw)].copy()
    if x.empty:
        raise ValueError("No FH samples in requested GW range")

    means=x.groupby(gw_col,as_index=False)[points_col].mean().rename(
        columns={points_col:"expected_fh_gain"}
    )
    x=x.merge(means,on=gw_col,how="left",validate="many_to_one")
    x["gw_offset"]=x[gw_col]-int(current_gw)
    x["reliability"]=np.power(config.future_discount,x.gw_offset)
    x["adjusted_points"]=x[points_col]*x.reliability

    winners=(x.sort_values(
        [sim_col,"adjusted_points",gw_col],ascending=[True,False,True]
    ).groupby(sim_col,sort=False).head(1))
    n_sim=int(x[sim_col].nunique())
    counts=winners[gw_col].value_counts().to_dict()

    rows=[]
    mean_map=dict(zip(means[gw_col],means.expected_fh_gain))
    for gw in range(int(current_gw),int(period_end_gw)+1):
        mean=mean_map.get(gw,float("nan"))
        reliability=float(config.future_discount**(gw-current_gw))
        rows.append(dict(
            gw=gw,
            probability_best=float(counts.get(gw,0)/n_sim),
            expected_fh_gain=float(mean) if not pd.isna(mean) else float("nan"),
            expected_adjusted_fh_gain=(float(mean)*reliability if not pd.isna(mean) else float("nan")),
            reliability=reliability,
        ))
    out=pd.DataFrame(rows)
    total=float(out.probability_best.sum())
    if not np.isclose(total,1.0,atol=1e-12):
        raise RuntimeError(f"FH GW probabilities do not sum to one: {total}")
    return out


def decide_fh_from_samples(
    samples: pd.DataFrame,
    *,
    current_gw: int,
    period_end_gw: int,
    config: ChipPlannerConfig = ChipPlannerConfig(),
    sim_col: str = "simulation",
    gw_col: str = "gw",
    points_col: str = "points",
) -> dict:
    """FH optimal-stopping rule, parallel to the TC rule.

    For the first chip period call with period_end_gw=19. If the chip is still
    unused at GW19 it is forced automatically.
    """
    probs=fh_opportunity_probabilities(
        samples,current_gw=current_gw,period_end_gw=period_end_gw,config=config,
        sim_col=sim_col,gw_col=gw_col,points_col=points_col,
    )
    cur=probs[probs.gw.eq(current_gw)]
    if cur.empty or pd.isna(cur.iloc[0].expected_fh_gain):
        raise ValueError(f"No FH value for current GW{current_gw}")
    cr=cur.iloc[0]
    use_now=float(cr.expected_fh_gain)
    future=probs[probs.gw.gt(current_gw)&probs.expected_adjusted_fh_gain.notna()]
    save_value=0.0 if future.empty else float(future.expected_adjusted_fh_gain.max())
    forced=(current_gw==period_end_gw)
    use=forced or (use_now>=save_value+config.min_use_edge)
    return dict(
        action="USE_FH" if use else "SAVE_FH",
        current_gw=int(current_gw),
        period_end_gw=int(period_end_gw),
        use_now_value=use_now,
        save_option_value=save_value,
        use_edge=use_now-save_value,
        probability_current_gw_best=float(cr.probability_best),
        forced_by_expiry=bool(forced),
        timing_probabilities=probs,
    )

def _fixed_tc_candidates(samples: pd.DataFrame, gw_col: str, points_col: str, id_col: str, name_col: str) -> tuple[pd.DataFrame,pd.DataFrame]:
    """Choose one TC candidate per GW ex ante by highest expected points."""
    means=(samples.groupby([gw_col,id_col,name_col],as_index=False)[points_col].mean())
    idx=means.groupby(gw_col,sort=True)[points_col].idxmax()
    chosen=means.loc[idx].rename(columns={points_col:'candidate_mean'}).reset_index(drop=True)
    x=samples.merge(chosen[[gw_col,id_col]],on=[gw_col,id_col],how='inner',validate='many_to_one')
    return x,chosen


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
    """Probability that each remaining GW is the best TC opportunity.

    The TC player for each GW is fixed before outcomes: the candidate with the
    highest expected points in that GW. Monte Carlo draws then answer how often
    each GW would turn out to be the best timing opportunity. Exactly one GW
    wins each simulation, so the probabilities sum to one by construction.
    """
    req={sim_col,gw_col,points_col,id_col}
    missing=req.difference(samples.columns)
    if missing:
        raise ValueError(f"TC samples missing columns: {sorted(missing)}")
    x=samples.copy()
    x[gw_col]=pd.to_numeric(x[gw_col],errors="raise").astype(int)
    x[points_col]=pd.to_numeric(x[points_col],errors="raise").astype(float)
    x=x[x[gw_col].between(current_gw,period_end_gw)].copy()
    if x.empty:
        raise ValueError("No TC samples in requested GW range")
    if name_col not in x:
        x[name_col]=x[id_col].astype(str)

    fixed,chosen=_fixed_tc_candidates(x,gw_col,points_col,id_col,name_col)
    fixed["gw_offset"]=fixed[gw_col]-int(current_gw)
    fixed["reliability"]=np.power(config.future_discount,fixed.gw_offset)
    fixed["adjusted_points"]=fixed[points_col]*fixed.reliability
    fixed=fixed.sort_values([sim_col,"adjusted_points",gw_col],ascending=[True,False,True])
    winners=fixed.groupby(sim_col,sort=False).head(1)
    n_sim=int(fixed[sim_col].nunique())
    counts=winners[gw_col].value_counts().to_dict()

    rows=[]
    for gw in range(int(current_gw),int(period_end_gw)+1):
        ch=chosen[chosen[gw_col].eq(gw)]
        g=fixed[fixed[gw_col].eq(gw)]
        if len(ch):
            cr=ch.iloc[0]
            cid=cr[id_col];cname=cr[name_col];mean=float(cr.candidate_mean)
            adjmean=float(mean*(config.future_discount**(gw-current_gw)))
        else:
            cid=None;cname=None;mean=float('nan');adjmean=float('nan')
        rows.append(dict(
            gw=gw,
            candidate_id=cid,
            candidate_name=cname,
            probability_best=float(counts.get(gw,0)/n_sim),
            expected_best_tc_points=mean,
            expected_adjusted_tc_points=adjmean,
            reliability=float(config.future_discount**(gw-current_gw)),
        ))
    out=pd.DataFrame(rows)
    total=float(out.probability_best.sum())
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
    """TC optimal-stopping rule without within-GW hindsight.

    One player per GW is chosen ex ante by highest mean xP. The timing
    probability distribution comes from that fixed player set. The save option
    is the highest uncertainty-discounted expected TC value in later GWs;
    future forecasts are recomputed when those GWs approach.
    """
    probs=tc_opportunity_probabilities(
        samples,current_gw=current_gw,period_end_gw=period_end_gw,config=config,
        sim_col=sim_col,gw_col=gw_col,points_col=points_col,id_col=id_col,name_col=name_col,
    )
    cur=probs[probs.gw.eq(current_gw)]
    if cur.empty or pd.isna(cur.iloc[0].expected_best_tc_points):
        raise ValueError(f"No TC candidates for current GW{current_gw}")
    cr=cur.iloc[0]
    use_now=float(cr.expected_best_tc_points)
    future=probs[probs.gw.gt(current_gw)&probs.expected_adjusted_tc_points.notna()]
    save_value=0.0 if future.empty else float(future.expected_adjusted_tc_points.max())
    use=(current_gw==period_end_gw) or (use_now>=save_value+config.min_use_edge)
    return dict(
        action="USE_TC" if use else "SAVE_TC",
        current_gw=int(current_gw),
        period_end_gw=int(period_end_gw),
        candidate_id=cr.candidate_id if use else None,
        candidate_name=cr.candidate_name if use else None,
        use_now_value=use_now,
        save_option_value=save_value,
        use_edge=use_now-save_value,
        probability_current_gw_best=float(cr.probability_best),
        timing_probabilities=probs,
    )
