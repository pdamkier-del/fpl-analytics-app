"""Stable Minute Model release contract for downstream PM/web consumers.

This module contains no model mathematics. It only normalizes a forecast table
into a versioned schema and validates hard invariants before release.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd

SCHEMA_VERSION="mm-release-v1"
REQUIRED_COLUMNS=[
    "season","gw","fixture_uuid","team_id","player_uuid","player","team","pos",
    "cutoff","p_start","xmins","expected_role","xi_assigned_role","xi_formation",
    "team_news_state","team_news_availability_cap",
]
OPTIONAL_COLUMNS=[
    "team_news_scoped_chance","team_news_age_hours","team_news_source",
    "p_cameo_given_bench","start_minutes_mean","cameo_minutes_mean",
    "model_version","generated_at",
]
ALLOWED_TEAM_NEWS={"AVAILABLE","RETURNED_AVAILABLE","DOUBT","MAJOR_DOUBT","OUT","SUSPENDED","UNKNOWN"}

@dataclass(frozen=True)
class ReleaseManifest:
    schema_version:str
    model_version:str
    generated_at:str
    rows:int
    fixtures:int
    teams:int
    players:int
    gw_min:int
    gw_max:int
    exact11_max_abs_error:float
    hard_out_positive_pstart_rows:int
    sha256_csv_gz:str|None=None

def normalize_mm_release(frame:pd.DataFrame,*,season="2025-26",model_version="UNLOCKED",
                         p_start_col="p_start",xmins_col="xmins")->pd.DataFrame:
    x=frame.copy()
    aliases={
        p_start_col:"p_start",xmins_col:"xmins",
        "normalized_availability_state":"team_news_state",
    }
    x=x.rename(columns={k:v for k,v in aliases.items() if k in x.columns and k!=v})
    if "season" not in x:x["season"]=season
    if "model_version" not in x:x["model_version"]=model_version
    if "generated_at" not in x:
        x["generated_at"]=datetime.now(timezone.utc).isoformat()
    defaults={
        "expected_role":"UNKNOWN","xi_assigned_role":"UNKNOWN","xi_formation":"UNKNOWN",
        "team_news_state":"UNKNOWN","team_news_availability_cap":1.0,
        "player":"","team":"","pos":"",
    }
    for c,v in defaults.items():
        if c not in x:x[c]=v
    missing=[c for c in REQUIRED_COLUMNS if c not in x.columns]
    if missing:raise ValueError(f"missing MM release columns: {missing}")
    ordered=REQUIRED_COLUMNS+[c for c in OPTIONAL_COLUMNS if c in x.columns]
    extra=[c for c in x.columns if c not in ordered]
    return x[ordered+extra].copy()

def validate_mm_release(frame:pd.DataFrame,*,exact11_tol=1e-6)->dict:
    x=frame.copy()
    missing=[c for c in REQUIRED_COLUMNS if c not in x.columns]
    if missing:raise ValueError(f"missing MM release columns: {missing}")
    if x.empty:raise ValueError("empty MM release")

    for c in ("p_start","xmins","team_news_availability_cap"):
        x[c]=pd.to_numeric(x[c],errors="coerce")
        if x[c].isna().any():raise ValueError(f"non-numeric/null {c}")
    if (~x.p_start.between(0,1)).any():raise ValueError("p_start outside 0..1")
    if (~x.xmins.between(0,90)).any():raise ValueError("xmins outside 0..90")
    if (~x.team_news_availability_cap.between(0,1)).any():
        raise ValueError("availability cap outside 0..1")
    if (x.p_start>x.team_news_availability_cap+1e-7).any():
        raise ValueError("p_start exceeds Team News availability cap")
    if (~x.team_news_state.astype(str).isin(ALLOWED_TEAM_NEWS)).any():
        raise ValueError("invalid Team News state")
    if x[["fixture_uuid","team_id","player_uuid"]].duplicated().any():
        raise ValueError("duplicate player/team/fixture row")
    if x[["fixture_uuid","team_id","player_uuid","gw","cutoff"]].isna().any().any():
        raise ValueError("null release identity/cutoff field")

    sums=x.groupby(["fixture_uuid","team_id"],sort=False).p_start.sum()
    exact_err=(sums-11.0).abs()
    maxerr=float(exact_err.max())
    if maxerr>exact11_tol:
        raise ValueError(f"exact-11 violated: max abs error {maxerr}")

    hard=x.team_news_state.isin(["OUT","SUSPENDED"])
    hard_positive=int((hard&(x.p_start>1e-9)).sum())
    if hard_positive:
        raise ValueError(f"{hard_positive} hard-out rows have positive p_start")

    # xMins must be zero if start and cameo opportunity are both impossible.
    impossible=x.team_news_availability_cap.le(1e-12)
    if (impossible&(x.xmins>1e-8)).any():
        raise ValueError("hard unavailable player has positive xmins")

    return {
        "rows":int(len(x)),
        "fixtures":int(x.fixture_uuid.nunique()),
        "teams":int(x.team_id.nunique()),
        "players":int(x.player_uuid.nunique()),
        "gw_min":int(pd.to_numeric(x.gw).min()),
        "gw_max":int(pd.to_numeric(x.gw).max()),
        "exact11_max_abs_error":maxerr,
        "hard_out_positive_pstart_rows":hard_positive,
    }

def write_mm_release(frame:pd.DataFrame,out_dir,*,model_version,season="2025-26",
                     p_start_col="p_start",xmins_col="xmins")->ReleaseManifest:
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    x=normalize_mm_release(frame,season=season,model_version=model_version,
                           p_start_col=p_start_col,xmins_col=xmins_col)
    stats=validate_mm_release(x)
    path=out/"mm_forecasts.csv.gz"
    x.to_csv(path,index=False,compression="gzip")
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest=ReleaseManifest(
        schema_version=SCHEMA_VERSION,model_version=model_version,
        generated_at=datetime.now(timezone.utc).isoformat(),
        sha256_csv_gz=digest,**stats)
    (out/"manifest.json").write_text(json.dumps(asdict(manifest),indent=2)+"\n")
    return manifest
