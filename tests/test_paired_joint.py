from dataclasses import asdict,replace
import numpy as np
from fpl_v1_1_model.paired_joint import build_pair,read_frozen_table,run_pair
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sample():
    f=read_frozen_table(ROOT/'analysis/results/joint-paired-inputs-v1','inputs')
    return f[f.fixture_uuid==f.fixture_uuid.iloc[0]].copy()


def test_pair_keeps_every_nonminute_input_identical():
    c,v=build_pair(sample())
    assert asdict(replace(c,players=()))==asdict(replace(v,players=()))
    allowed={'p_start','p_cameo_given_bench','start_minutes_mean','cameo_minutes_mean'}
    for x,y in zip(c.players,v.players):
        assert {k:z for k,z in asdict(x).items() if k not in allowed}=={k:z for k,z in asdict(y).items() if k not in allowed}


def test_identical_arms_reproduce_exactly_with_same_seed():
    c,_=build_pair(sample())
    x,y=run_pair(c,c,n=10,seed=42)
    assert x==y


def test_pair_rejects_duplicate_roster_and_invalid_minutes_identity():
    f=sample()
    for bad in [f.iloc[np.r_[0,np.arange(len(f))]].copy(),f.assign(v4_workload_start_xmins=91.0)]:
        try:build_pair(bad)
        except ValueError:pass
        else:raise AssertionError('Invalid pair accepted')
