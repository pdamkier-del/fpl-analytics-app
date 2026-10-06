#!/usr/bin/env python3
"""Audit locked-MM errors by realised team formation and realised starter role."""
from pathlib import Path
import json
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
PRED=ROOT/"analysis/results/mm-gw-player-error-audit-20261006-v1/all_player_gw_predictions.csv.gz"
ROLES=ROOT/"analysis/results/reproducible-role-v1/classified_starters.csv"
OUT=ROOT/"analysis/results/mm-formation-role-error-audit-20261006-v1"

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    p=pd.read_csv(PRED)
    r=pd.read_csv(ROLES)
    team_form=(r[["fixture_uuid","team_id","formation"]]
               .drop_duplicates()
               .rename(columns={"formation":"actual_formation"}))
    actual_role=(r[["fixture_uuid","team_id","player_uuid","final_role","slot_role","position_role","role_confidence","disagreement"]]
                 .rename(columns={"final_role":"actual_role_posthoc"}))
    x=p.merge(team_form,on=["fixture_uuid","team_id"],how="left",validate="many_to_one")
    x=x.merge(actual_role,on=["fixture_uuid","team_id","player_uuid"],how="left",validate="one_to_one")
    x["actual_role_posthoc"]=x.actual_role_posthoc.fillna("UNOBSERVED_BENCH")
    x["role_match"]=np.where(x.actual_start.eq(1),x.expected_role.eq(x.actual_role_posthoc),np.nan)
    x["abs_min_error"]=(x.xmins-x.minutes).abs()
    x["start_abs_error"]=(x.p_start-x.actual_start).abs()

    byf=x.groupby("actual_formation",dropna=False).agg(
        rows=("player_uuid","size"),
        starters=("actual_start","sum"),
        xmins_mae=("abs_min_error","mean"),
        start_mae=("start_abs_error","mean"),
        high_p_nonstart=("error_bucket",lambda s:int((s=="HIGH_PSTART_DID_NOT_START").sum())),
        low_p_start=("error_bucket",lambda s:int((s=="LOW_PSTART_STARTED").sum())),
    ).reset_index().sort_values("xmins_mae",ascending=False)
    byf.to_csv(OUT/"by_actual_formation.csv",index=False)

    starters=x[x.actual_start.eq(1)].copy()
    byr=starters.groupby(["actual_role_posthoc"],dropna=False).agg(
        starts=("player_uuid","size"),
        xmins_mae=("abs_min_error","mean"),
        start_mae=("start_abs_error","mean"),
        expected_role_match_rate=("role_match","mean"),
    ).reset_index().sort_values("xmins_mae",ascending=False)
    byr.to_csv(OUT/"by_actual_role.csv",index=False)

    mism=starters[starters.expected_role.ne(starters.actual_role_posthoc)].copy()
    mism=mism.sort_values("abs_min_error",ascending=False)
    mism.to_csv(OUT/"starter_role_mismatches.csv",index=False)

    pairs=(mism.groupby(["expected_role","actual_role_posthoc"]).agg(
        n=("player_uuid","size"),
        xmins_mae=("abs_min_error","mean"),
        start_mae=("start_abs_error","mean")
    ).reset_index().sort_values(["n","xmins_mae"],ascending=[False,False]))
    pairs.to_csv(OUT/"role_mismatch_pairs.csv",index=False)

    byteam=(x.groupby("team").agg(
        rows=("player_uuid","size"),
        xmins_mae=("abs_min_error","mean"),
        formation_count=("actual_formation","nunique"),
        starter_role_match_rate=("role_match","mean")
    ).reset_index().sort_values("xmins_mae",ascending=False))
    byteam.to_csv(OUT/"by_team.csv",index=False)

    summary={
        "rows":int(len(x)),
        "formations":int(x.actual_formation.nunique()),
        "starters":int(starters.shape[0]),
        "starter_role_match_rate":float(starters.role_match.mean()),
        "starter_role_mismatches":int(len(mism)),
        "unknown_expected_role_starts":int((starters.expected_role=="UNKNOWN").sum()),
        "unknown_actual_role_starts":int((starters.actual_role_posthoc=="UNKNOWN").sum()),
    }
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
