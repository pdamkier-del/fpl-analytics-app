"""Paired seeded PM parity on archived fixtures; adapter only, no model edits."""
from dataclasses import asdict
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from fpl_v1_1_model.paired_joint import read_frozen_table
from fpl_v1_1_model.fixture_input import prepare_fixture
from fpl_v1_1_model.canonical_fixture_input import prepare_canonical_fixture, LEGACY_ALIASES
from fpl_v1_1_model.joint_simulator import simulate_many

ROOT=Path(__file__).resolve().parents[1]

def _prepare_frame(g):
    frame=g.copy(deep=True)
    frame["lambda_pen"]=.1
    frame["team_pen_conversion"]=.8
    frame["pen_weight"]=.2
    frame["pen_conversion"]=.8
    frame["bg_mean_rate90"]=5.
    frame["bg_sd90"]=2.
    for a,b in (
      ("v4_workload_start_p_start","control_p_start"),
      ("v4_workload_start_xmins","control_xmins"),
      ("v4_p_cameo_given_bench","p_cameo_given_bench"),
      ("v4_start_minutes_mean","start_minutes_mean"),
      ("v4_cameo_minutes_mean","cameo_minutes_mean")):
        frame[a]=frame[b]
    return frame

def _canonicalize(frame):
    out=frame.copy(deep=True)
    out["p_start"]=out["control_p_start"]
    out["xmins"]=out["control_xmins"]
    return out.drop(columns=list(LEGACY_ALIASES))

def test_archived_multi_fixture_seeded_parity():
    data=read_frozen_table(ROOT/"analysis/results/joint-paired-inputs-v1","inputs")
    assert len(data)>0
    fixtures=data.fixture_uuid.drop_duplicates().tolist()
    assert len(fixtures)>=6, "Need at least six unique archived fixtures"
    selected=fixtures[:6]
    for fid in selected:
        frame=_prepare_frame(data[data.fixture_uuid.eq(fid)])
        old=prepare_fixture(frame,p_keeper_save_given_miss=.5,bps_rules="2026-27").model_input
        new=prepare_canonical_fixture(_canonicalize(frame),
                                      p_keeper_save_given_miss=.5,bps_rules="2026-27").model_input
        assert asdict(old)==asdict(new), "Input mismatch for "+fid
        a=simulate_many(old,n=128,seed=83114)
        b=simulate_many(new,n=128,seed=83114)
        assert a==b, "Seeded xP mismatch for "+fid
