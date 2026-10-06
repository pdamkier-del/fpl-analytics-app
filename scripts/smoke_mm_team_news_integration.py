#!/usr/bin/env python3
"""Smoke-check certified Team News hand-off against the MM feature universe.

This does NOT run a forecast simulation. It validates the historical strict
ledger can be reconstructed, joined cutoff-safely, and converted to availability.
"""
from pathlib import Path
import json,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"scripts"))

from fpl_v1_1_model.team_news_history import read_split_gzip_jsonl,build_strict_team_news_features
from run_mm_unified_official_roles import SOURCE

FOLDER=ROOT/"data_v1_1/derived/team_news_audit/2025-26-v2"

def main():
    strict=read_split_gzip_jsonl(FOLDER)
    assert len(strict)==28960
    assert strict.gw.min()==2 and strict.gw.max()==38
    assert strict.player_uuid.notna().all()

    frame=pd.read_csv(SOURCE).reset_index(drop=True)
    merged=build_strict_team_news_features(frame,strict)
    known=merged.team_news_known.eq(1)
    assert not known.any() or pd.to_datetime(merged.loc[known,"team_news_effective_at"],utc=True).lt(
        pd.to_datetime(merged.loc[known,"cutoff"],utc=True)).all()
    assert merged.team_news_availability_cap.between(0,1).all()
    covered=sorted(int(x) for x in merged.loc[known,"gw"].unique())
    assert all(g in covered for g in range(2,39))
    assert 1 not in covered

    result={
        "strict_rows":int(len(strict)),
        "model_rows":int(len(merged)),
        "known_model_rows":int(known.sum()),
        "hard_out_model_rows":int(merged.team_news_hard_out.sum()),
        "covered_gws":covered,
        "states":{str(k):int(v) for k,v in merged.loc[known,"team_news_state"].value_counts().to_dict().items()},
        "max_age_hours":float(merged.loc[known,"team_news_age_hours"].max()) if known.any() else None,
        "no_target_leakage":True,
        "caps_in_unit_interval":True,
        "simulation_run":False,
    }
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
