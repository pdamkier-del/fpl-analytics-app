#!/usr/bin/env python3
"""Fail-closed integration gate joining current-season MM and PM evidence.

The historical replay entrypoint hardcodes 2025-26 sources and 2242-point
replay assertions, so it must NOT be used to label live output. This bridge
checks 2026-27 provenance before a later unchanged PM simulator invocation.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"data_v1_1/derived/live_locked_inputs/2026-27-v1"
WORK=ROOT/"work/live-final-model"
COMPONENTS={
 "mm":WORK/"mm_frozen_diagnostic_six_gw.csv.gz",
 "player_events":BASE/"vfinal_player_event_components_6gw.csv.gz",
 "team_goals":BASE/"future_team_goal_lambdas.csv.gz",
 "keeper_saves":BASE/"keeper_lambda_saves_by_fixture_team.csv.gz",
}
def inspect(source,read_csv=pd.read_csv):
    checked={}
    for name,path in source.items():
        if not path.exists():
            checked[name]={"present":False}
            continue
        df=read_csv(path,low_memory=False)
        checked[name]={"present":True,"rows":len(df),"columns":list(df.columns)}
        if df.empty:raise ValueError(f"{name}: empty data")
    mm=read_csv(source["mm"],low_memory=False) if source["mm"].exists() else None
    if mm is not None:
        required={"fixture_uuid","player_uuid","team_id","target_gw","p_start","xmins"}
        if required-set(mm):raise ValueError("MM missing keys: "+str(required-set(mm)))
        if mm.duplicated(["fixture_uuid","player_uuid"]).any():
            raise ValueError("Duplicate MM player/fixture")
        if not mm.target_gw.between(int(mm.gw.min()),min(38,int(mm.gw.min())+5)).all():
            raise ValueError("MM outside current six-GW horizon")
    for name in ("player_events",):
        if source[name].exists() and mm is not None:
            events=read_csv(source[name],low_memory=False)
            if {"fixture_uuid","player_uuid"}-set(events):raise ValueError("PM event identities missing")
            a=set(zip(mm.fixture_uuid.astype(str),mm.player_uuid.astype(str)))
            b=set(zip(events.fixture_uuid.astype(str),events.player_uuid.astype(str)))
            if a!=b:raise ValueError("MM/PM player-fixture identity mismatch")
    blockers=[f"Missing {k}" for k,v in checked.items() if not v["present"]]
    blockers.extend(["Frozen vFinal joint simulator has not been executed and audited on these inputs",
      "Verified 2026-27 penalty takers and BPS background must be supplied",
      "Same-origin TS v3 / FH / WC / BB / TC run required before publication"])
    return {"status":"live_model_integration_diagnostic_only",
      "components":checked,"blockers":blockers,
      "xpts_calculated":False,"locked_model_active":False}

def main():
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path,default=WORK/"live_model_integration_gate.json")
    a=p.parse_args()
    result=inspect(COMPONENTS)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"available":{k:v["present"] for k,v in result["components"].items()},"blockers":result["blockers"]}))
if __name__=="__main__":main()
