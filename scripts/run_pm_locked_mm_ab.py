#!/usr/bin/env python3
"""Paired PM simulation with old vs locked Team News MM.

PM mathematics and all non-minute components stay frozen. The only change is
the Minute Model input, rebuilt walk-forward for each GW22-38 cutoff.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"scripts"))

from fpl_v1_1_model.paired_joint import read_frozen_table,run_pair
from fpl_v1_1_model.rating_history import build_rating_features
from fpl_v1_1_model.team_news_history import read_split_gzip_jsonl,build_strict_team_news_features
from run_mm_unified_official_roles import SOURCE
from run_v4_performance_rating_experiment import build_perf_ledger,add_features as add_perf_features
from run_v4_three_state_sequence_experiment import add_sequence_features,write_json
from run_mm_v2_team_news_availability_experiment import evaluate_news_variant
from run_vfinal_integrated import (
    build_final_frame,make_vfinal_input,score,bonus_metrics,FROZEN
)

RATINGS=ROOT/"data_v1_1/derived/mm_v2_ratings/player_match_ratings.csv.gz"
TEAM_NEWS=ROOT/"data_v1_1/derived/team_news_audit/2025-26-v2"
OUT=ROOT/"analysis/results/pm-locked-mm-ab-20261007-v1"
POLICY="soft_0.5_0.1"
KEYS=["fixture_uuid","player_uuid","team_id"]

def build_locked_mm_predictions():
    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    frame=build_rating_features(frame,pd.read_csv(RATINGS))
    strict=read_split_gzip_jsonl(TEAM_NEWS,"predeadline_strict.jsonl.gz")
    frame=build_strict_team_news_features(frame,strict)
    known=pd.to_datetime(frame.outcome_known_at,utc=True)

    rows=[]
    for gw in range(22,39):
        val=frame.gw.eq(gw).to_numpy()
        if not val.any(): continue
        cut=pd.to_datetime(frame.loc[val,"cutoff"],utc=True).min()
        train=((frame.gw<gw)&(known<cut)).to_numpy()
        feat,p_locked,x_locked,p_pre,p_news,x_news,q,sub,met=evaluate_news_variant(
            frame,train,val,POLICY)
        part=feat.loc[val,KEYS+["gw","player","team","pos","minutes","y",
                                "team_news_state","team_news_availability_cap"]].copy()
        part["new_p_start"]=p_news[val]
        part["new_xmins"]=x_news[val]
        part["new_q_sub"]=q[val]
        part["new_sub_minutes"]=sub[val]
        part["old_locked_p_start"]=p_locked[val]
        part["old_locked_xmins"]=x_locked[val]
        rows.append(part)
        print("MM GW",gw,"done",flush=True)
    return pd.concat(rows,ignore_index=True)

def metric_block(sc,prefix):
    return {
      "nonbonus":score(sc.total_points-sc.bonus,sc[f"{prefix}_nonbonus"]),
      "total_xpts":score(sc.total_points,sc[f"{prefix}_xpts"]),
      "bonus":bonus_metrics(sc.bonus.astype(int),
                            sc[f"{prefix}_p1"],sc[f"{prefix}_p2"],sc[f"{prefix}_p3"])
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    old=build_final_frame()
    mm=build_locked_mm_predictions()
    mm.to_csv(OUT/"locked_mm_predictions.csv.gz",index=False,compression="gzip")

    # Exact cohort and one-to-one integration.
    use=mm[KEYS+["new_p_start","new_xmins","new_q_sub","new_sub_minutes",
                 "team_news_state","team_news_availability_cap"]]
    new=old.merge(use,on=KEYS,how="left",validate="one_to_one")
    if new[["new_p_start","new_xmins","new_q_sub","new_sub_minutes"]].isna().any().any():
        miss=new[new.new_p_start.isna()][KEYS+["gw"]].head(20).to_dict(orient="records")
        raise ValueError(f"Missing locked-MM rows: {miss}")

    new["v4_workload_start_p_start"]=new.new_p_start
    new["v4_workload_start_xmins"]=new.new_xmins
    new["v4_p_cameo_given_bench"]=new.new_q_sub
    new["v4_cameo_minutes_mean"]=new.new_sub_minutes

    # PM A/B: same PM math, same fixtures, paired MC seeds.
    truth=read_frozen_table(FROZEN,"targets")
    rows=[]
    for i,fx in enumerate(sorted(old.fixture_uuid.unique())):
        og=old[old.fixture_uuid==fx]
        ng=new[new.fixture_uuid==fx]
        oi,_=make_vfinal_input(og)
        ni,_=make_vfinal_input(ng)
        ro,rn=run_pair(oi,ni,n=400,seed=73192001+i)
        for r in ng.itertuples(index=False):
            pid=str(r.player_uuid)
            rows.append({
              "fixture_uuid":fx,"player_uuid":pid,"gw":int(r.gw),"pos":r.pos,
              "actual_minutes":float(r.minutes),
              "old_p_start":float(og.loc[og.player_uuid.astype(str).eq(pid),"combined_p_start"].iloc[0]),
              "new_p_start":float(r.new_p_start),
              "old_xmins_input":float(og.loc[og.player_uuid.astype(str).eq(pid),"combined_xmins"].iloc[0]),
              "new_xmins_input":float(r.new_xmins),
              "old_nonbonus":ro[pid]["xPts_nonbonus"],
              "new_nonbonus":rn[pid]["xPts_nonbonus"],
              "old_xpts":ro[pid]["xPts"],"new_xpts":rn[pid]["xPts"],
              "old_bonus":ro[pid]["expected_bonus"],"new_bonus":rn[pid]["expected_bonus"],
              "old_p1":ro[pid]["p_bonus_1"],"old_p2":ro[pid]["p_bonus_2"],"old_p3":ro[pid]["p_bonus_3"],
              "new_p1":rn[pid]["p_bonus_1"],"new_p2":rn[pid]["p_bonus_2"],"new_p3":rn[pid]["p_bonus_3"],
              "old_pm_minutes":ro[pid]["expected_minutes"],
              "new_pm_minutes":rn[pid]["expected_minutes"],
            })
        print("PM fixture",i+1,"/",old.fixture_uuid.nunique(),flush=True)

    pred=pd.DataFrame(rows)
    sc=pred.merge(truth,on=["fixture_uuid","player_uuid"],validate="one_to_one")
    pred.to_csv(OUT/"predictions.csv.gz",index=False,compression="gzip")

    oldm=metric_block(sc,"old");newm=metric_block(sc,"new")
    result={
      "classification":"paired PM A/B; frozen vFinal PM, only MM changed",
      "gws":[int(sc.gw.min()),int(sc.gw.max())],
      "fixtures":int(sc.fixture_uuid.nunique()),"rows":int(len(sc)),
      "draws_per_fixture":400,
      "old_mm":"v4 combined minutes used by current vFinal",
      "new_mm":"locked Team News MM soft_0.5_0.1, weekly walk-forward",
      "old":oldm,"new":newm,
      "delta_total_xpts":{k:newm["total_xpts"][k]-oldm["total_xpts"][k] for k in ["mae","rmse","bias"]},
      "delta_nonbonus":{k:newm["nonbonus"][k]-oldm["nonbonus"][k] for k in ["mae","rmse","bias"]},
      "delta_bonus":{k:newm["bonus"][k]-oldm["bonus"][k] for k in ["log_loss","brier","mae","rmse"]},
      "PM_math_changed":False,
      "TS_changed":False,
      "diagnostic_warning":"GW22-38 is reused same-season diagnostic, not pristine external holdout."
    }

    # Position and GW stability.
    pos=[];gwr=[]
    for posname,g in sc.groupby("pos"):
        a=score(g.total_points,g.old_xpts);b=score(g.total_points,g.new_xpts)
        pos.append({"pos":posname,"n":len(g),"old_mae":a["mae"],"new_mae":b["mae"],
                    "delta_mae":b["mae"]-a["mae"],"old_rmse":a["rmse"],
                    "new_rmse":b["rmse"],"delta_rmse":b["rmse"]-a["rmse"]})
    for gw,g in sc.groupby("gw"):
        a=score(g.total_points,g.old_xpts);b=score(g.total_points,g.new_xpts)
        gwr.append({"gw":int(gw),"n":len(g),"old_mae":a["mae"],"new_mae":b["mae"],
                    "delta_mae":b["mae"]-a["mae"],"old_rmse":a["rmse"],
                    "new_rmse":b["rmse"],"delta_rmse":b["rmse"]-a["rmse"]})
    pd.DataFrame(pos).to_csv(OUT/"by_position.csv",index=False)
    pd.DataFrame(gwr).to_csv(OUT/"by_gw.csv",index=False)

    # Hauls and error attribution.
    sc["old_abs_err"]=(sc.old_xpts-sc.total_points).abs()
    sc["new_abs_err"]=(sc.new_xpts-sc.total_points).abs()
    sc["gain_abs_err"]=sc.old_abs_err-sc.new_abs_err
    sc["minute_gain"]=(sc.old_xmins_input-sc.actual_minutes).abs()-(sc.new_xmins_input-sc.actual_minutes).abs()
    hauls=sc[sc.total_points>=10].copy()
    result["haul_10plus"]={
      "rows":int(len(hauls)),
      "old_mae":float(hauls.old_abs_err.mean()) if len(hauls) else None,
      "new_mae":float(hauls.new_abs_err.mean()) if len(hauls) else None,
      "delta_mae":float(hauls.new_abs_err.mean()-hauls.old_abs_err.mean()) if len(hauls) else None,
      "mean_minute_gain":float(hauls.minute_gain.mean()) if len(hauls) else None,
      "improved_rows":int((hauls.gain_abs_err>0).sum()) if len(hauls) else 0,
      "worsened_rows":int((hauls.gain_abs_err<0).sum()) if len(hauls) else 0,
    }
    hauls.sort_values("total_points",ascending=False).to_csv(OUT/"haul_10plus.csv",index=False)

    # Rows where MM moved materially, to distinguish minute-driven PM changes.
    moved=sc[(sc.new_xmins_input-sc.old_xmins_input).abs()>=10].copy()
    result["material_mm_changes"]={
      "rows":int(len(moved)),
      "mean_old_minute_abs_error":float((moved.old_xmins_input-moved.actual_minutes).abs().mean()) if len(moved) else None,
      "mean_new_minute_abs_error":float((moved.new_xmins_input-moved.actual_minutes).abs().mean()) if len(moved) else None,
      "old_pm_mae":float(moved.old_abs_err.mean()) if len(moved) else None,
      "new_pm_mae":float(moved.new_abs_err.mean()) if len(moved) else None,
    }
    moved.sort_values("gain_abs_err",ascending=False).to_csv(OUT/"material_mm_changes.csv",index=False)

    write_json(OUT/"result.json",result)
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
