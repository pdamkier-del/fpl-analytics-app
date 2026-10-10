"""Opt-in live release boundary for verified impossible appearances.

Frozen MM parameters, training and compose() are NOT modified. This
module only changes the *inputs* to unchanged compose() after the
locked forecast has run. This is an explicitly versioned prospective
availability interpretation, not a claim that replay math is identical.
Never apply origin-GW6 news to later GW7..11 without a fresh scoped source.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .mm_release import validate_mm_release

HARD_STATES=frozenset(("OUT","SUSPENDED"))
BOUNDARY_VERSION="live-hard-eligibility-v1-candidate"


def prepare_live_mm_release_candidate(
    frame: pd.DataFrame,
    *,
    p_start,
    q_sub,
    sub_minutes,
    origin_gw: int,
    news_scoped_gw: int,
) -> pd.DataFrame:
    """Return a NEW MM release candidate with a sourced hard-availability gate.

    Leave the frozen model's p/q/duration estimates untouched in provenance
    fields. Re-compose expected minutes with q_sub_effective=0 only when
    availability is documented as impossible. Require news scoped to the
    forecast GW; never propagate it across future GWs implicitly.
    """
    from run_mm_unified_official_roles import compose  # same unmodified frozen formula

    needed={"gw","team_news_state","team_news_availability_cap","start_minutes_mean",
            "p_start","xmins"}
    missing=needed-set(frame.columns)
    if missing:raise ValueError(f"missing original MM fields: {sorted(missing)}")
    if not isinstance(origin_gw,int) or not 1<=origin_gw<=38:
        raise ValueError("invalid origin gameweek")
    if news_scoped_gw!=origin_gw:
        raise ValueError("news is not scoped to this origin gameweek")
    x=frame.copy(deep=True)
    if x.empty or x.gw.isna().any() or not x.gw.eq(origin_gw).all():
        raise ValueError("one-GW scoped news cannot be reused for other GWs")
    p=np.asarray(p_start,dtype=float)
    q=np.asarray(q_sub,dtype=float)
    sub=np.asarray(sub_minutes,dtype=float)
    caps=pd.to_numeric(x.team_news_availability_cap,errors="coerce").to_numpy(float)
    mins=pd.to_numeric(x.xmins,errors="coerce").to_numpy(float)
    if any(len(v)!=len(x) for v in (p,q,sub,caps,mins)):
        raise ValueError("model output length differs from frame")
    if (not all(np.isfinite(v).all() for v in (p,q,sub,caps,mins))
        or np.any((p<0)|(p>1))
        or np.any((q<0)|(q>1))
        or np.any((caps<0)|(caps>1))
        or np.any(sub<0)):
        raise ValueError("invalid model output or availability inputs")
    if not np.allclose(p,x.p_start.to_numpy(float),rtol=0,atol=1e-9):
        raise ValueError("p_start not identical to locked forecast")
    original=np.asarray(compose(x,p,q,sub),dtype=float)
    if not np.allclose(original,mins,rtol=0,atol=1e-7):
        raise ValueError("raw minutes do not match unchanged frozen compose()")
    states=x.team_news_state.astype(str)
    hard=states.isin(HARD_STATES).to_numpy()
    impossible=hard | (caps<=1e-12)
    if np.any(hard & (caps>1e-12)):
        raise ValueError("hard-out state not reflected in availability cap")
    if np.any(impossible & (p>1e-9)):
        raise ValueError("hard-unavailable player has positive start chance")
    gated_q=np.where(impossible,0.0,q)
    minutes=np.asarray(compose(x,p,gated_q,sub),dtype=float)
    if np.any(minutes[impossible]>1e-8):
        raise ValueError("hard-unavailable player still has positive minutes")
    x["mm_raw_xmins"]=original
    x["mm_raw_q_sub"]=q
    x["live_effective_q_sub"]=gated_q
    x["live_eligibility_minutes_removed"]=original-minutes
    x["live_eligibility_applied"]=impossible
    x["live_eligibility_rule"]=BOUNDARY_VERSION
    x["xmins"]=minutes
    validate_mm_release(x)  # still enforce exact XI and hard-ineligible rules
    return x
