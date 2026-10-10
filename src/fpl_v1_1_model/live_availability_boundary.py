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
BOUNDARY_VERSION="live-hard-eligibility-v1"


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


def validate_scoped_official_news(frame: pd.DataFrame, ledger: pd.DataFrame, *, origin_gw: int) -> dict:
    """Require real player-level cutoff-safe Team News before any *live* release.

    Ledger schema is the collector's official season/GW player snapshot.
    All MM players must be present in that same origin GW, not merely
    assumed from a command-line flag. No inferred later-GW OUT decisions.
    """
    required={"player_uuid","gw","team_news_state","cutoff"}
    needed_ledger={"player_uuid","gw","normalized_availability_state",
                   "observed_at","cutoff","source","source_id","timing_verified"}
    if missing:=required-set(frame.columns):
        raise ValueError(f"MM table missing scoped news columns: {sorted(missing)}")
    if missing:=needed_ledger-set(ledger.columns):
        raise ValueError(f"Team News ledger missing columns: {sorted(missing)}")
    if frame.empty or not frame.gw.eq(origin_gw).all():
        raise ValueError("MM target GW mismatches official news origin GW")
    if ledger.empty:
        raise ValueError("Team News ledger is empty")
    ledger=ledger.copy(deep=True)
    ledger["gw"]=pd.to_numeric(ledger.gw,errors="coerce")
    if ledger.gw.isna().any():
        raise ValueError("Team News GW is invalid")
    ledger=ledger.loc[ledger.gw.eq(origin_gw)].copy()
    if ledger.empty or ledger.player_uuid.isna().any():
        raise ValueError("No valid official Team News scoped to origin GW")
    if ledger.player_uuid.duplicated().any():
        raise ValueError("Ambiguous duplicate Team News for a player/GW")
    news=ledger.set_index("player_uuid")
    players=frame.player_uuid.astype(str)
    if not players.isin(news.index).all():
        raise ValueError("MM player missing official scoped Team News observation")
    aligned=news.reindex(players).reset_index(drop=True)
    if not aligned.normalized_availability_state.astype(str).eq(frame.team_news_state.astype(str).reset_index(drop=True)).all():
        raise ValueError("MM availability differs from official scoped Team News ledger")
    if not aligned.timing_verified.eq(True).all():
        raise ValueError("Unverified Team News timing")
    if not aligned.source.astype(str).eq("Official FPL bootstrap-static").all():
        raise ValueError("Expected captured official FPL Team News source")
    if aligned.source_id.isna().any() or aligned.source_id.astype(str).str.strip().eq("").any():
        raise ValueError("Missing Team News source ID")
    origin_cut=pd.to_datetime(frame.cutoff,errors="coerce",utc=True)
    observed=pd.to_datetime(aligned.observed_at,errors="coerce",utc=True)
    official_deadline=pd.to_datetime(aligned.cutoff,errors="coerce",utc=True)
    if origin_cut.isna().any() or observed.isna().any() or official_deadline.isna().any():
        raise ValueError("Invalid Team News timestamp")
    if (observed.to_numpy()>origin_cut.to_numpy()).any() or (observed>official_deadline).any():
        raise ValueError("Post-cutoff Team News is not allowed")
    return {"official_news_gw":int(origin_gw),
            "players_with_verified_news":int(len(set(players))),
            "official_news_rows":int(len(ledger)),
            "official_news_capture_max":observed.max().isoformat()}
