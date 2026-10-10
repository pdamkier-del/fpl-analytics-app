#!/usr/bin/env python3
"""Build frozen sequence features for 2026/27 using observed prior FPL stats.

Calls the EXISTING locked feature builder add_sequence_features. Unknown target
outcomes are not used (a future sentinel exclusively in the transient build
table) and are never emitted. No new model mathematics.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"scripts")]
from run_v4_three_state_sequence_experiment import add_sequence_features,SEQ_FEATURES

BASE=ROOT/"data_v1_1/derived/live_locked_inputs/2026-27-v1"
RAW=BASE/"source_feature_matrix.csv.gz"
PAST=BASE/"player_fixture_observations.csv.gz"
OUT=BASE/"sequence_feature_matrix.csv.gz"


def build():
    target=pd.read_csv(RAW,low_memory=False)
    history=pd.read_csv(PAST,low_memory=False)
    required_target={"fixture_uuid","player_uuid","cutoff","target_gw","gw"}
    required_history={"fixture_uuid","player_uuid","available_at","started","minutes","gw"}
    if not required_target.issubset(target):
        raise ValueError("Live source missing IDs and cutoff")
    if not required_history.issubset(history):
        raise ValueError("Official completed FPL observations lack prior-state inputs")
    if target.empty or history.empty:
        raise ValueError("No live targets or completed historical observations")
    assert not target.duplicated(["fixture_uuid","player_uuid"]).any()
    origin=int(target.gw.iloc[0])
    if not target.gw.eq(origin).all():
        raise ValueError("Live historical news must share one origin gameweek")
    if history.gw.ge(origin).any():
        raise ValueError("Current or future GW observations in historical source")
    history=history.copy()
    history["outcome_known_at"]=pd.to_datetime(history.available_at,utc=True,errors="raise")
    origin_cut=pd.to_datetime(target.cutoff,utc=True,errors="raise")
    if origin_cut.isna().any():
        raise ValueError("Invalid forecast cutoff")
    history=history[history.outcome_known_at<origin_cut.min()].copy()
    if history.empty:
        raise ValueError("No pre-cutoff actual PL sequence evidence")
    history["y"]=pd.to_numeric(history.started,errors="coerce")
    history["minutes"]=pd.to_numeric(history.minutes,errors="coerce")
    if history[["y","minutes"]].isna().any().any():
        raise ValueError("Completed season history has missing start/minutes evidence")
    if not history.y.isin([0,1]).all() or (~history.minutes.between(0,90)).any():
        raise ValueError("Invalid confirmed starts/minutes in FPL history")
    assert not history.duplicated(["fixture_uuid","player_uuid"]).any()
    # Read-only target stand-ins exclusively for the frozen SEQUENCE builder.
    # Future sentinel prevents a target being used as another target's history.
    stub=target[["player_uuid","cutoff"]].copy()
    stub["outcome_known_at"]=pd.Timestamp("2100-01-01T00:00:00Z")
    stub["y"]=0
    stub["minutes"]=0.
    train=history[["player_uuid","outcome_known_at","y","minutes"]].copy()
    train["cutoff"]=train.outcome_known_at + pd.Timedelta(seconds=1)
    combo=pd.concat([train,stub],ignore_index=True)
    made=add_sequence_features(combo)
    assert len(made)==len(train)+len(target)
    features=made.loc[len(train):,SEQ_FEATURES].reset_index(drop=True)
    if not np.isfinite(features.to_numpy(float)).all():
        raise ValueError("Non-finite frozen sequence features")
    if any(f in target for f in SEQ_FEATURES):
        raise ValueError("Sequence feature overwrite forbidden")
    result=pd.concat([target.reset_index(drop=True),features],axis=1)
    if result.duplicated(["fixture_uuid","player_uuid"]).any() or len(result)!=len(target):
        raise ValueError("Sequence linkage broke fixture/player identity")
    assert "y" not in result and "outcome_known_at" not in result
    OUT.parent.mkdir(parents=True,exist_ok=True)
    result.to_csv(OUT,index=False,compression="gzip")
    print("FROZEN LIVE SEQUENCE FEATURES",json.dumps({
        "origin_gw":origin,"target_rows":len(result),
        "completed_observations":len(history),"features_added":len(SEQ_FEATURES),
        "sequence_rows_with_history":int((result.seq_hist_n>0).sum()),
        "unknown_target_outcomes_used":0,
        "feature_file":str(OUT.relative_to(ROOT))}),flush=True)
    return result


if __name__=="__main__":
    build()
