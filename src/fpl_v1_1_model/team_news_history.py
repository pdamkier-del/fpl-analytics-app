"""Cutoff-safe FPL/PL Team News history.

The ledger is append-only. Each row is an observation that became known at
observed_at. Forecasts may only use observations with observed_at <= cutoff.

This module intentionally contains no tuned P(start) weights.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import pandas as pd

NORMALIZED_STATES=(
    "AVAILABLE","RETURNED_AVAILABLE","DOUBT","MAJOR_DOUBT",
    "OUT","SUSPENDED","UNKNOWN"
)

@dataclass(frozen=True)
class TeamNewsState:
    player_uuid:str
    observed_at:pd.Timestamp
    normalized_state:str
    raw_status:str=""
    raw_news:str=""
    chance_this_round:float|None=None
    chance_next_round:float|None=None
    source:str=""
    source_id:str=""
    carried_forward:bool=False

    @property
    def hard_out(self)->bool:
        return self.normalized_state in {"OUT","SUSPENDED"}

def _prob(v):
    if v is None or (isinstance(v,float) and math.isnan(v)): return None
    try: x=float(v)
    except Exception: return None
    if x>1: x/=100.0
    return min(1.0,max(0.0,x))

def normalize_team_news(raw_status=None,raw_news=None,chance_this_round=None):
    s=str(raw_status or "").strip().lower()
    n=str(raw_news or "").strip().lower()
    c=_prob(chance_this_round)

    if s in {"s","suspended"} or "suspend" in n:
        return "SUSPENDED"
    if s in {"i","u","out","injured","unavailable"}:
        return "OUT"
    hard_terms=("ruled out","will miss","not available","unavailable","out for","sidelined")
    if any(t in n for t in hard_terms):
        return "OUT"

    returned_terms=("available again","back in training","returned to training","fit again","available for selection")
    if any(t in n for t in returned_terms):
        return "RETURNED_AVAILABLE"

    if s in {"a","available","fit"} and c is None:
        return "AVAILABLE"

    if c is not None:
        if c<=0.25: return "MAJOR_DOUBT"
        if c<1.0: return "DOUBT"
        return "AVAILABLE"

    doubt_terms=("doubt","late fitness test","fitness test","touch and go","unlikely")
    if any(t in n for t in doubt_terms):
        return "DOUBT"
    if s in {"d","doubtful"}:
        return "DOUBT"
    if s in {"a","available","fit"}:
        return "AVAILABLE"
    return "UNKNOWN"

def default_availability_cap(state:str,chance_this_round=None)->float:
    c=_prob(chance_this_round)
    if state in {"OUT","SUSPENDED"}: return 0.0
    if c is not None: return c
    if state=="MAJOR_DOUBT": return 0.25
    if state=="DOUBT": return 0.75
    return 1.0

def validate_team_news_ledger(ledger:pd.DataFrame)->pd.DataFrame:
    required={"player_uuid","observed_at"}
    missing=required-set(ledger.columns)
    if missing: raise ValueError(f"missing Team News columns: {sorted(missing)}")
    x=ledger.copy()
    x["player_uuid"]=x.player_uuid.astype(str)
    x["observed_at"]=pd.to_datetime(x.observed_at,utc=True,errors="coerce")
    if x.observed_at.isna().any(): raise ValueError("invalid observed_at")
    if "effective_at" in x:
        eff=pd.to_datetime(x.effective_at,utc=True,errors="coerce")
        if eff.isna().any(): raise ValueError("invalid effective_at")
        if (eff>x.observed_at).any():
            raise ValueError("effective_at cannot be after observed_at")
    for c in ("raw_status","raw_news","source","source_id"):
        if c not in x: x[c]=""
    for c in ("chance_this_round","chance_next_round"):
        if c not in x: x[c]=float("nan")
    if "normalized_availability_state" not in x:
        x["normalized_availability_state"]=[
            normalize_team_news(a,b,c) for a,b,c in
            zip(x.raw_status,x.raw_news,x.chance_this_round)
        ]
    bad=~x.normalized_availability_state.isin(NORMALIZED_STATES)
    if bad.any(): raise ValueError("invalid normalized availability state")
    dup_cols=["player_uuid","observed_at","source","source_id"]
    if x.duplicated(dup_cols).any():
        raise ValueError("duplicate Team News observation")
    return x.sort_values(["player_uuid","observed_at","source","source_id"]).reset_index(drop=True)

def latest_team_news_before(ledger:pd.DataFrame,player_uuid:str,cutoff,max_age_days:float|None=None):
    x=validate_team_news_ledger(ledger)
    cut=pd.to_datetime(cutoff,utc=True)
    g=x[(x.player_uuid==str(player_uuid))&(x.observed_at<=cut)]
    if g.empty: return None
    row=g.iloc[-1]
    age=(cut-row.observed_at).total_seconds()/86400
    if max_age_days is not None and age>max_age_days: return None
    return TeamNewsState(
        player_uuid=str(row.player_uuid),observed_at=row.observed_at,
        normalized_state=str(row.normalized_availability_state),
        raw_status=str(row.raw_status or ""),raw_news=str(row.raw_news or ""),
        chance_this_round=_prob(row.chance_this_round),
        chance_next_round=_prob(row.chance_next_round),
        source=str(row.source or ""),source_id=str(row.source_id or ""),
        carried_forward=age>0,
    )

def build_team_news_features(targets:pd.DataFrame,ledger:pd.DataFrame,*,max_age_days=None)->pd.DataFrame:
    x=validate_team_news_ledger(ledger)
    out=targets.copy()
    states=[];caps=[];ages=[];sources=[];raw=[];carry=[]
    for r in out.itertuples(index=False):
        st=latest_team_news_before(x,str(r.player_uuid),getattr(r,"cutoff"),max_age_days=max_age_days)
        if st is None:
            states.append("UNKNOWN");caps.append(1.0);ages.append(float("nan"))
            sources.append("");raw.append("");carry.append(0.0)
            continue
        cut=pd.to_datetime(getattr(r,"cutoff"),utc=True)
        states.append(st.normalized_state)
        caps.append(default_availability_cap(st.normalized_state,st.chance_this_round))
        ages.append((cut-st.observed_at).total_seconds()/86400)
        sources.append(st.source);raw.append(st.raw_news);carry.append(float(st.carried_forward))
    out["team_news_state"]=states
    out["team_news_availability_cap"]=caps
    out["team_news_age_days"]=ages
    out["team_news_source"]=sources
    out["team_news_raw"]=raw
    out["team_news_carried_forward"]=carry
    out["team_news_known"]=(out.team_news_state!="UNKNOWN").astype(float)
    out["team_news_hard_out"]=out.team_news_state.isin(["OUT","SUSPENDED"]).astype(float)
    return out
