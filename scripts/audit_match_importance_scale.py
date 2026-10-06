#!/usr/bin/env python3
"""Audit Match Importance scale without changing MM mathematics."""
from __future__ import annotations
import json,sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from fpl_v1_1_model.match_importance import (
 BASE_COMPETITION_VALUES,dynamic_competition_value,knockout_stage_strength,
 premier_league_stage_strength,opponent_strength_from_elo,
)
from fpl_v1_1_model.future_match_importance import load_gw_schedule_snapshots

OUT=ROOT/"analysis/results/mi-scale-audit-20261006-v1"
RAW=ROOT/"data_v1_1/raw/all-competitions-2025-26"
TEAMS=ROOT/"data_v1_1/derived/mm_v2_ratings/identity_source/data/2025-2026/teams.csv"

STAGES=[
 ("league_phase",.36),("playoff",.55),("round_of_16",.64),
 ("quarter_final",.76),("semi_final",.88),("final",1.00),
]
COMPS=["champions-league","europa-league","conference-league","fa-cup","efl-cup"]

def score(comp,stage,opp=.5,active=None,eta=.35):
    active=active or list(BASE_COMPETITION_VALUES)
    cv=dynamic_competition_value(comp,active,eta=eta)
    return .45*cv+.30*stage+.25*opp

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for comp in COMPS:
        for stage_name,stage in STAGES:
            rows.append({
              "competition":comp,"stage":stage_name,"stage_strength":stage,
              "competition_value_all_active":dynamic_competition_value(comp,list(BASE_COMPETITION_VALUES)),
              "importance_neutral_opponent":score(comp,stage),
            })
    scale=pd.DataFrame(rows)
    scale.to_csv(OUT/"current_scale.csv",index=False)

    # Dynamic competition value examples.
    scenarios={
      "all_active":list(BASE_COMPETITION_VALUES),
      "prem_ucl_fa":["prem","champions-league","fa-cup"],
      "prem_ucl":["prem","champions-league"],
      "ucl_only":["champions-league"],
      "prem_fa":["prem","fa-cup"],
      "fa_only":["fa-cup"],
    }
    dyn=[]
    for label,active in scenarios.items():
        for comp in active:
            dyn.append({
              "scenario":label,"active":"|".join(active),"competition":comp,
              "dynamic_cv":dynamic_competition_value(comp,active),
              "final_importance_neutral_opp":score(comp,1.0,active=active),
            })
    pd.DataFrame(dyn).to_csv(OUT/"dynamic_competition_examples.csv",index=False)

    teams=pd.read_csv(TEAMS)
    code_to_team={int(r.code):int(r.id) for r in teams.itertuples(index=False)}
    snaps=load_gw_schedule_snapshots(RAW,code_to_team)
    snap_rows=[]
    for gw,s in snaps.items():
        if s.empty: continue
        z=s.copy()
        z["gw_snapshot"]=gw
        z["has_round_name"]="round_name" in z.columns and z["round_name"].notna()
        snap_rows.append(z)
    snap=pd.concat(snap_rows,ignore_index=True)
    nonprem=snap[snap.competition.ne("prem")]
    has_round=bool("round_name" in nonprem.columns)
    round_nonnull=int(nonprem["round_name"].notna().sum()) if has_round else 0

    # Quantify how much stage can move the final importance score.
    deltas=[]
    for comp in COMPS:
        vals={n:score(comp,v) for n,v in STAGES}
        deltas.append({
          "competition":comp,
          **{k:vals[k] for k,_ in STAGES},
          "league_to_final_delta":vals["final"]-vals["league_phase"],
          "semi_to_final_delta":vals["final"]-vals["semi_final"],
        })
    pd.DataFrame(deltas).to_csv(OUT/"stage_deltas.csv",index=False)

    summary={
      "classification":"MI scale audit; no model changes",
      "current_formula":"0.45*dynamic_competition_value + 0.30*stage + 0.25*opponent_strength",
      "stage_weights":{"league_phase":.36,"playoff":.55,"round_of_16":.64,
                       "quarter_final":.76,"semi_final":.88,"final":1.0},
      "snapshot_nonprem_rows":int(len(nonprem)),
      "snapshot_has_round_name_column":has_round,
      "snapshot_nonnull_round_name_rows":round_nonnull,
      "stage_fallback_is_month_based":not has_round or round_nonnull==0,
      "ucl_neutral_all_active":{
        n:score("champions-league",v) for n,v in STAGES
      },
      "fa_neutral_all_active":{
        n:score("fa-cup",v) for n,v in STAGES
      },
      "efl_neutral_all_active":{
        n:score("efl-cup",v) for n,v in STAGES
      },
      "conclusion":[
        "Forward schedule snapshots do not carry explicit round/stage in current loader.",
        "Stage contributes only 30% of final MI, making semi-to-final separation small.",
        "Before retuning Future MI, stage identity should be made cutoff-safe and stage scale tested separately."
      ]
    }
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
