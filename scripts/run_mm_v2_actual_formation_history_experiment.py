#!/usr/bin/env python3
"""MM experiment: use actual historical formations in expected-XI selection.

Historical per-match player roles are already encoded in q/H from the role ledger.
This experiment adds the missing team-level signal: recency-weighted actual
formation history before each cutoff.

Selection is development-only (GW16-21). GW22-38 is reused diagnostic only.
PM/TS and duration models remain unchanged.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"scripts"))

from fpl_v1_1_model.formation_history import history_from_classified_starters
from fpl_v1_1_model.rating_history import build_rating_features
from run_mm_v2_relative_rating_competition import evaluate_variant
from run_mm_unified_official_roles import SOURCE
from run_v4_performance_rating_experiment import build_perf_ledger,add_features as add_perf_features
from run_v4_three_state_sequence_experiment import add_sequence_features,write_json

RATING_CFG={"name":"relative_self_trend","gamma":.02,"rel_w":.65,"self_w":.25,"trend_w":.10}
RATINGS=ROOT/"data_v1_1/derived/mm_v2_ratings/player_match_ratings.csv.gz"
ROLES_LEDGER=ROOT/"analysis/results/reproducible-role-v1/classified_starters.csv"
OUT=ROOT/"analysis/results/mm-v2-actual-formation-history-20261006-v1"

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    frame=build_rating_features(frame,pd.read_csv(RATINGS))
    formations=history_from_classified_starters(pd.read_csv(ROLES_LEDGER))

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev=frame.gw.between(16,21).to_numpy()
    dcut=pd.to_datetime(frame.loc[dev,"cutoff"],utc=True).min()
    dtr=(frame.gw.between(6,15)&(known<dcut)).to_numpy()

    # Reference = selected XI + relative ratings, but no formation prior.
    _,_,_,_,_,_,ref_rows,_,_=evaluate_variant(
        frame,dtr,dev,RATING_CFG,l2s=(.5,))
    ref=ref_rows.iloc[0].to_dict()

    rows=[]
    for half_life in (2.0,3.0,5.0,8.0,12.0):
        for strength in (.10,.25,.50,1.0,1.5,2.0):
            _,_,_,_,_,_,cand,_,_=evaluate_variant(
                frame,dtr,dev,RATING_CFG,l2s=(.5,),
                formation_history=formations,
                formation_half_life=half_life,
                formation_strength=strength)
            met=cand.iloc[0].to_dict()
            row={"half_life":half_life,"strength":strength,**met}
            for k in ["state_log_loss","state_brier","xmins_mae","xmins_rmse"]:
                row["delta_vs_relative_"+k]=met[k]-ref[k]
            rows.append(row)

    grid=pd.DataFrame(rows).sort_values(
        ["delta_vs_relative_state_log_loss","delta_vs_relative_xmins_rmse","delta_vs_relative_xmins_mae"])
    grid.to_csv(OUT/"development_grid.csv",index=False)

    eligible=grid[
        (grid.delta_vs_relative_state_log_loss<0)&
        (grid.delta_vs_relative_xmins_rmse<=.02)&
        (grid.delta_vs_relative_xmins_mae<=.02)
    ]
    selected=None if eligible.empty else eligible.iloc[0].to_dict()

    result={
        "classification":"MM v2 actual historical formation prior experiment",
        "reference":"XI + bounded relative ratings",
        "reference_development":ref,
        "selected":selected,
        "development_grid":grid.to_dict(orient="records"),
        "rules":{
            "historical_formation_from_completed_matches_only":True,
            "historical_player_roles_already_feed_q_H":True,
            "formation_history_cutoff_safe":True,
            "PM_TS_unchanged":True,
            "duration_models_unchanged":True,
            "GW22_38_reused_diagnostic_only":True
        }
    }

    if selected is not None:
        test=frame.gw.between(22,38).to_numpy()
        tcut=pd.to_datetime(frame.loc[test,"cutoff"],utc=True).min()
        ttr=(frame.gw.between(6,21)&(known<tcut)).to_numpy()
        _,_,_,_,_,_,base_rows,_,_=evaluate_variant(
            frame,ttr,test,RATING_CFG,l2s=(.5,))
        _,_,_,_,_,_,form_rows,_,_=evaluate_variant(
            frame,ttr,test,RATING_CFG,l2s=(.5,),
            formation_history=formations,
            formation_half_life=float(selected["half_life"]),
            formation_strength=float(selected["strength"]))
        base=base_rows.iloc[0].to_dict();met=form_rows.iloc[0].to_dict()
        result["reused_diagnostic"]={
            "relative_rating":base,
            "formation_history":met,
            "delta":{k:met[k]-base[k] for k in ["state_log_loss","state_brier","xmins_mae","xmins_rmse","xmins_bias"]}
        }

    write_json(OUT/"result.json",result)
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
