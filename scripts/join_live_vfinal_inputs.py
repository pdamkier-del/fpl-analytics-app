#!/usr/bin/env python3
"""Join frozen live PM ingredients by *real* fixture / player identities.

Produces an audited simulator input table, not xP. Refuses to fabricate
missing player, penalty, bonus-background or team-level parameters.
"""
from pathlib import Path
import argparse, hashlib, json
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"data_v1_1/derived/live_locked_inputs/2026-27-v1"
WORK=ROOT/"work/live-final-model"

def combine(mm, events, teams, saves):
    required={
        "mm":{"fixture_uuid","player_uuid","team_id","target_gw","xmins","p_start","pos"},
        "events":{"fixture_uuid","player_uuid","goal_rate90","assist_rate90","mu_dc"},
        "teams":{"fpl_fixture_id","home_team_id","away_team_id","lambda_home_goals","lambda_away_goals"},
        "saves":{"fixture_uuid","team_id","lambda_saves"}}
    frames={"mm":mm,"events":events,"teams":teams,"saves":saves}
    for name,df in frames.items():
        missing=required[name]-set(df.columns)
        if missing:raise ValueError(f"{name} missing {sorted(missing)}")
    keys=["fixture_uuid","player_uuid"]
    for name,df,ukey in [
        ("mm",mm,keys),("events",events,keys),
        ("teams",teams,["fpl_fixture_id"]),("saves",saves,["fixture_uuid","team_id"])]:
        if df.duplicated(ukey).any():raise ValueError(f"Duplicate {name} keys")
    if set(map(tuple,mm[keys].astype(str).to_numpy()))!=set(map(tuple,events[keys].astype(str).to_numpy())):
        raise ValueError("Missing or additional player event fixture identities")
    # Preserve all frozen PM event signals, including disciplinary and DefCon
    # fields. Earlier code silently discarded these and prevented vFinal input
    # assembly. Shared columns must agree instead of being overwritten.
    overlaps=sorted((set(events.columns)&set(mm.columns))-set(keys))
    for col in overlaps:
        compare=mm[keys+[col]].merge(events[keys+[col]],on=keys,
                      how="inner",validate="one_to_one",suffixes=("_mm","_pm"))
        left=compare[col+"_mm"];right=compare[col+"_pm"]
        if not left.equals(right):
            raise ValueError("MM/PM conflicting shared field "+col)
    event_fields=[col for col in events.columns if col not in mm.columns or col in keys]
    merged=mm.merge(events[event_fields],on=keys,validate="one_to_one",how="inner")
    t=teams.copy()
    t["fixture_uuid"]="live-2026-27-fpl-"+t.fpl_fixture_id.astype(int).astype(str)
    required_fixtures=set(merged.fixture_uuid.astype(str))
    if set(t.fixture_uuid)!=required_fixtures:
        raise ValueError("Team goal input and MM use different fixture IDs")
    merged=merged.merge(t[["fixture_uuid","home_team_id","away_team_id",
                             "lambda_home_goals","lambda_away_goals"]],
                        on="fixture_uuid",validate="many_to_one")
    if not ((merged.team_id==merged.home_team_id)|(merged.team_id==merged.away_team_id)).all():
        raise ValueError("Player team not participating in fixture")
    merged["opponent_team_id"]=merged.away_team_id.where(
        merged.team_id==merged.home_team_id,merged.home_team_id)
    expected_sides=set(map(tuple,merged[["fixture_uuid","team_id"]].drop_duplicates().astype(str).to_numpy()))
    got_sides=set(map(tuple,saves[["fixture_uuid","team_id"]].astype(str).to_numpy()))
    if expected_sides!=got_sides:raise ValueError("Keeper model team sides do not match")
    merged=merged.merge(saves[["fixture_uuid","team_id","lambda_saves"]],
                        on=["fixture_uuid","team_id"],how="left",validate="many_to_one")
    for col in ["xmins","p_start","goal_rate90","assist_rate90","mu_dc",
                "lambda_home_goals","lambda_away_goals","lambda_saves"]:
        if merged[col].isna().any():raise ValueError("Missing simulator component "+col)
    return merged

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,default=BASE/"vfinal_live_joined_inputs.csv.gz")
    args=ap.parse_args()
    paths=dict(mm=WORK/"mm_frozen_diagnostic_six_gw.csv.gz",
        events=BASE/"vfinal_player_event_components_6gw.csv.gz",
        teams=BASE/"future_team_goal_lambdas.csv.gz",
        saves=BASE/"keeper_lambda_saves_by_fixture_team.csv.gz")
    inputs={k:pd.read_csv(p,low_memory=False) for k,p in paths.items()}
    joined=combine(**inputs)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    joined.to_csv(args.out,index=False,compression="gzip")
    evidence={"classification":"INCOMPLETE_VFINAL_SIMULATOR_INPUT_NO_XP",
       "origin_gw":int(joined.target_gw.min()),"rows":len(joined),
       "fixtures":int(joined.fixture_uuid.nunique()),
       "gws":sorted(map(int,joined.target_gw.unique())),
       "input_sha256":{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()},
       "xpts_calculated":False,"locked_model_active":False,
       "blocking_components":["penalty taker state", "BPS background distribution",
                              "complete original vFinal joint fixture construction"]}
    (WORK/"live_vfinal_joined_manifest.json").write_text(json.dumps(evidence,indent=2)+"\n")
    print(json.dumps(evidence))

if __name__=="__main__":main()
