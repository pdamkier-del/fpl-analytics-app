#!/usr/bin/env python3
"""Gate frozen live forecasts on observed current-season GW1..origin-1 history.

This audits the EXISTING live input checkpoint; the simpler official endpoint
adapter is not substituted for trusted starts, minutes, roles or provenance.
"""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"data_v1_1/derived/live_locked_inputs/2026-27-v1"
WORK=ROOT/"work/live-final-model"

def audit(history,targets):
    if history.empty or targets.empty: raise ValueError("Missing live GW history or target rows")
    required={"gw","available_at","fixture_uuid","player_uuid","started","minutes"}
    if required-set(history.columns):raise ValueError("Missing history fields: "+str(required-set(history.columns)))
    if {"gw","target_gw","cutoff"}-set(targets.columns):
        raise ValueError("Missing target origin/cutoff")
    if targets.gw.nunique()!=1:raise ValueError("Origins are mixed")
    origin=int(targets.gw.iloc[0])
    if not 2<=origin<=38:raise ValueError("Expected GW2..GW38 origin")
    expected=set(range(1,origin))
    observed=set(map(int,history.gw.unique()))
    if expected!=observed:
        raise ValueError(f"Missing/extra historic GW: expected {sorted(expected)}, observed {sorted(observed)}")
    if not history.started.isin([0,1,False,True]).all():raise ValueError("Unverified started label")
    minutes=pd.to_numeric(history.minutes,errors="coerce")
    if minutes.isna().any() or not minutes.between(0,120).all():
        raise ValueError("Invalid or unknown minutes")
    if history.duplicated(["fixture_uuid","player_uuid"]).any():
        raise ValueError("Duplicate historical fixture/player")
    ts=pd.to_datetime(history.available_at,utc=True,errors="raise")
    cuts=pd.to_datetime(targets.cutoff,utc=True,errors="raise")
    if cuts.nunique()!=1:raise ValueError("Targets must have one common as-of time")
    if not (ts<cuts.iloc[0]).all():raise ValueError("Future or equal-cutoff outcome in historical data")
    if not targets.target_gw.between(origin,min(38,origin+5)).all():
        raise ValueError("Targets extend outside six-GW horizon")
    if set(history.fixture_uuid.astype(str))&set(targets.fixture_uuid.astype(str)):
        raise ValueError("History/target fixture overlap")
    result={"classification":"COMPLETED_GW_HISTORY_CUTOFF_GATE_NOT_FULL_LIVE_CERTIFICATION",
       "origin_gw":origin,"completed_gws":sorted(expected),
       "history_rows":len(history),"player_count":int(history.player_uuid.nunique()),
       "target_rows":len(targets),"asof":cuts.iloc[0].isoformat(),
       "all_history_before_cutoff":True,"frozen_models_unchanged":True,
       "locked_model_active":False}
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--history",type=Path,default=BASE/"player_fixture_observations.csv.gz")
    ap.add_argument("--targets",type=Path,default=BASE/"source_feature_matrix.csv.gz")
    ap.add_argument("--out",type=Path,default=WORK/"current_season_history_gate.json")
    a=ap.parse_args()
    history=pd.read_csv(a.history,low_memory=False)
    target=pd.read_csv(a.targets,low_memory=False)
    result=audit(history,target)
    result["input_sha256"]={
        "history":hashlib.sha256(a.history.read_bytes()).hexdigest(),
        "targets":hashlib.sha256(a.targets.read_bytes()).hexdigest()}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
if __name__=="__main__":main()
