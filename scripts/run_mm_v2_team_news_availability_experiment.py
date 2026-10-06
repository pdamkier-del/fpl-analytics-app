#!/usr/bin/env python3
"""MM v2 Team News availability experiment using the certified strict projection.

Pipeline:
  locked MM -> strict Team News availability -> XI + relative ratings
  -> residual P(start) -> strict availability enforced again -> xMins.

Selection is development-only (GW16-21). GW22-38 is reused diagnostic only.
This script is not run by the integration smoke workflow.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"scripts"))

from fpl_v1_1_model.rating_history import build_rating_features
from fpl_v1_1_model.team_news_history import (
    read_split_gzip_jsonl,build_strict_team_news_features,strict_state_cap
)
from fpl_v1_1_model.availability_projection import project_exact_starters_with_caps
from run_mm_v2_relative_rating_competition import add_relative_xi_features,evaluate_variant
from run_mm_v2_xi_rating_experiment import ASSIGN_FEATURES,fit_residual,compose
from run_mm_unified_official_roles import SOURCE,full_mm
from run_v4_performance_rating_experiment import build_perf_ledger,add_features as add_perf_features
from run_v4_three_state_sequence_experiment import add_sequence_features,metrics,write_json,write_gzip_csv

OUT_DEFAULT=ROOT/"analysis/results/mm-v2-team-news-availability-20261006-v2"
TEAM_NEWS_DEFAULT=ROOT/"data_v1_1/derived/team_news_audit/2025-26-v2"
RATING_CFG={"name":"relative_self_trend","gamma":.02,"rel_w":.65,"self_w":.25,"trend_w":.10}
L2=.5

def policy_caps(frame,policy):
    st=frame.team_news_state.astype(str)
    chance=frame.team_news_scoped_chance
    if policy=="hard_only":
        return np.where(st.isin(["OUT","SUSPENDED"]),0.0,1.0)
    if policy=="source_chance":
        return np.array([
            strict_state_cap(s,c,doubt_cap=1.0,major_doubt_cap=1.0)
            for s,c in zip(st,chance)
        ],dtype=float)
    if policy.startswith("soft_"):
        _,doubt,major=policy.split("_")
        d=float(doubt);m=float(major)
        return np.array([
            strict_state_cap(s,c,doubt_cap=d,major_doubt_cap=m)
            for s,c in zip(st,chance)
        ],dtype=float)
    raise ValueError(policy)

def evaluate_news_variant(frame,train,val,policy):
    p_locked,q,sub,x_locked,_=full_mm(frame.copy(),train)
    caps=policy_caps(frame,policy)

    # Team News affects the competition state before the XI optimizer sees it.
    p_pre_xi=project_exact_starters_with_caps(frame,p_locked,caps)
    feat=add_relative_xi_features(frame,p_pre_xi,RATING_CFG)

    p_residual,_=fit_residual(feat,p_pre_xi,train,ASSIGN_FEATURES,L2)

    # Residual fitting must never revive a player above certified availability.
    p_news=project_exact_starters_with_caps(feat,p_residual,caps)
    x_news=compose(feat,p_news,q,sub)
    met=metrics(feat,val,p_news,q,x_news)
    return feat,p_locked,x_locked,p_pre_xi,p_news,x_news,q,sub,met

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ratings",required=True)
    ap.add_argument("--team-news-folder",default=str(TEAM_NEWS_DEFAULT))
    ap.add_argument("--out",default=str(OUT_DEFAULT))
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)

    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    frame=build_rating_features(frame,pd.read_csv(a.ratings))

    strict=read_split_gzip_jsonl(Path(a.team_news_folder),"predeadline_strict.jsonl.gz")
    frame=build_strict_team_news_features(frame,strict)

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev=frame.gw.between(16,21).to_numpy()
    dcut=pd.to_datetime(frame.loc[dev,"cutoff"],utc=True).min()
    dtr=(frame.gw.between(6,15)&(known<dcut)).to_numpy()

    # Existing selected XI+relative-rating model is the development reference.
    _,_,_,_,_,_,ref_rows,_,_=evaluate_variant(frame,dtr,dev,RATING_CFG,l2s=(L2,))
    ref=ref_rows.iloc[0].to_dict()

    policies=["hard_only","source_chance"]
    for d in (.50,.65,.75,.85,.95):
        for m in (.10,.25,.40,.55):
            policies.append(f"soft_{d}_{m}")

    rows=[]
    for policy in policies:
        try:
            *_,met=evaluate_news_variant(frame,dtr,dev,policy)
            rec={"policy":policy,"valid":True,**met}
            for k in ["state_log_loss","state_brier","xmins_mae","xmins_rmse"]:
                rec["delta_vs_relative_"+k]=met[k]-ref[k]
            rows.append(rec)
        except ValueError as exc:
            rows.append({"policy":policy,"valid":False,"error":str(exc)})

    grid=pd.DataFrame(rows)
    valid=grid[grid.valid.eq(True)].copy()
    valid=valid.sort_values(["state_log_loss","xmins_rmse","xmins_mae"])
    grid.to_csv(out/"development_grid.csv",index=False)

    selected=None
    if len(valid):
        eligible=valid[
            (valid.delta_vs_relative_state_log_loss<0)&
            (valid.delta_vs_relative_xmins_rmse<=.05)&
            (valid.delta_vs_relative_xmins_mae<=.05)
        ]
        if len(eligible):
            selected=eligible.iloc[0].to_dict()

    result={
        "classification":"MM v2 certified strict Team News availability experiment",
        "reference":"selected XI + bounded relative ratings",
        "reference_development":ref,
        "selected":selected,
        "development_grid":grid.to_dict(orient="records"),
        "coverage":{
            "strict_source_rows":int(len(strict)),
            "known_model_rows":int(frame.team_news_known.sum()),
            "hard_out_model_rows":int(frame.team_news_hard_out.sum()),
            "total_model_rows":int(len(frame)),
            "covered_gws":sorted(int(x) for x in frame.loc[frame.team_news_known.eq(1),"gw"].unique()),
        },
        "rules":{
            "strict_tier_only":True,
            "gw1_missing_is_neutral":True,
            "scoped_chance_only":True,
            "unknown_is_neutral":True,
            "availability_applied_before_XI":True,
            "availability_reapplied_after_residual":True,
            "exact_11_preserved":True,
            "duration_models_unchanged":True,
            "PM_TS_unchanged":True,
            "GW22_38_reused_diagnostic_only":True,
        }
    }

    if selected is not None:
        policy=str(selected["policy"])
        test=frame.gw.between(22,38).to_numpy()
        tcut=pd.to_datetime(frame.loc[test,"cutoff"],utc=True).min()
        ttr=(frame.gw.between(6,21)&(known<tcut)).to_numpy()

        _,_,_,_,_,_,ref_test,_,_=evaluate_variant(frame,ttr,test,RATING_CFG,l2s=(L2,))
        ref_met=ref_test.iloc[0].to_dict()
        feat,p_locked,x_locked,p_pre_xi,p_news,x_news,q,sub,met=evaluate_news_variant(
            frame,ttr,test,policy)

        result["reused_diagnostic"]={
            "relative_rating":ref_met,
            "team_news":met,
            "delta":{k:met[k]-ref_met[k] for k in
                     ["state_log_loss","state_brier","xmins_mae","xmins_rmse","xmins_bias"]}
        }
        pred=feat.loc[test,[
            "fixture_uuid","player_uuid","team_id","gw","team","player","pos",
            "expected_role","xi_assigned_role","xi_formation","y","minutes",
            "team_news_state","team_news_scoped_chance","team_news_availability_cap",
            "team_news_age_hours","team_news_source"
        ]].copy()
        pred["locked_p_start"]=p_locked[test]
        pred["pre_xi_availability_p_start"]=p_pre_xi[test]
        pred["team_news_p_start"]=p_news[test]
        pred["locked_xmins"]=x_locked[test]
        pred["team_news_xmins"]=x_news[test]
        write_gzip_csv(pred,out/"reused_diagnostic_predictions.csv.gz")

    write_json(out/"result.json",result)
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
