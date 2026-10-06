#!/usr/bin/env python3
"""MM v2 Team News availability experiment.

Input is an append-only cutoff-safe Team News ledger. The experiment leaves the
locked duration/sub models unchanged and layers availability on top of the
selected XI + bounded relative-rating P(start).

Selection is development-only (GW16-21). GW22-38 is reused diagnostic only.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"scripts"))

from fpl_v1_1_model.rating_history import build_rating_features
from fpl_v1_1_model.team_news_history import build_team_news_features
from fpl_v1_1_model.availability_projection import project_exact_starters_with_caps
from run_mm_v2_relative_rating_competition import evaluate_variant
from run_mm_unified_official_roles import SOURCE
from run_v4_performance_rating_experiment import build_perf_ledger,add_features as add_perf_features
from run_v4_three_state_sequence_experiment import add_sequence_features,metrics,write_json,write_gzip_csv
from run_mm_v2_xi_rating_experiment import compose

OUT_DEFAULT=ROOT/"analysis/results/mm-v2-team-news-availability-20261006-v1"
RATING_CFG={"name":"relative_self_trend","gamma":.02,"rel_w":.65,"self_w":.25,"trend_w":.10}
L2=.5

def policy_caps(frame,policy):
    st=frame.team_news_state.astype(str)
    chance=frame.team_news_availability_cap.to_numpy(float)
    if policy=="hard_only":
        return np.where(st.isin(["OUT","SUSPENDED"]),0.0,1.0)
    if policy=="source_chance":
        return chance
    if policy.startswith("soft_"):
        _,doubt,major=policy.split("_")
        doubt=float(doubt);major=float(major)
        out=np.ones(len(frame),dtype=float)
        out[st.isin(["OUT","SUSPENDED"])]=0.0
        out[st.eq("DOUBT")]=np.minimum(chance[st.eq("DOUBT")],doubt)
        out[st.eq("MAJOR_DOUBT")]=np.minimum(chance[st.eq("MAJOR_DOUBT")],major)
        return out
    raise ValueError(policy)

def run_partition(frame,train,val,policy):
    feat,p0,q,sub,x0,base,cand,models,preds=evaluate_variant(
        frame,train,val,RATING_CFG,l2s=(L2,))
    p_rel,x_rel=preds[L2]
    caps=policy_caps(feat,policy)
    p_news=project_exact_starters_with_caps(feat,p_rel,caps)
    x_news=compose(feat,p_news,q,sub)
    return feat,p_rel,x_rel,p_news,x_news,metrics(feat,val,p_rel,q,x_rel),metrics(feat,val,p_news,q,x_news)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ratings",required=True)
    ap.add_argument("--team-news",required=True)
    ap.add_argument("--out",default=str(OUT_DEFAULT))
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)

    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    frame=build_rating_features(frame,pd.read_csv(a.ratings))
    frame=build_team_news_features(frame,pd.read_csv(a.team_news))

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev=frame.gw.between(16,21).to_numpy()
    dcut=pd.to_datetime(frame.loc[dev,"cutoff"],utc=True).min()
    dtr=(frame.gw.between(6,15)&(known<dcut)).to_numpy()

    policies=["hard_only","source_chance"]
    for d in (.50,.65,.75,.85):
        for m in (.10,.25,.40):
            policies.append(f"soft_{d}_{m}")

    rows=[];cache={}
    for policy in policies:
        try:
            vals=run_partition(frame,dtr,dev,policy)
        except ValueError as exc:
            rows.append({"policy":policy,"valid":False,"error":str(exc)})
            continue
        feat,p_rel,x_rel,p_news,x_news,base,met=vals
        rec={"policy":policy,"valid":True,**met}
        for k in ["state_log_loss","state_brier","xmins_mae","xmins_rmse"]:
            rec["delta_vs_relative_"+k]=met[k]-base[k]
        rows.append(rec);cache[policy]=vals

    grid=pd.DataFrame(rows)
    valid=grid[grid.valid==True].copy()
    valid=valid.sort_values(["state_log_loss","xmins_rmse","xmins_mae"])
    grid.to_csv(out/"development_grid.csv",index=False)

    selected=None
    if len(valid):
        better=valid[
            (valid.delta_vs_relative_state_log_loss<0)&
            (valid.delta_vs_relative_xmins_rmse<=.05)&
            (valid.delta_vs_relative_xmins_mae<=.05)
        ]
        if len(better): selected=better.iloc[0].to_dict()

    result={
        "classification":"MM v2 Team News availability experiment",
        "base":"selected XI + bounded relative ratings",
        "selected":selected,
        "development_grid":grid.to_dict(orient="records"),
        "coverage":{
            "known_rows":int(frame.team_news_known.sum()),
            "hard_out_rows":int(frame.team_news_hard_out.sum()),
            "carried_forward_rows":int(frame.team_news_carried_forward.sum()),
            "total_rows":int(len(frame)),
        },
        "rules":{
            "cutoff_safe_latest_observation_only":True,
            "unknown_is_neutral":True,
            "availability_before_exact_11_projection":True,
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
        feat,p_rel,x_rel,p_news,x_news,base,met=run_partition(frame,ttr,test,policy)
        result["reused_diagnostic"]={
            "relative_rating":base,
            "team_news":met,
            "delta":{k:met[k]-base[k] for k in ["state_log_loss","state_brier","xmins_mae","xmins_rmse","xmins_bias"]}
        }
        pred=feat.loc[test,["fixture_uuid","player_uuid","team_id","gw","team","player","pos",
                            "expected_role","y","minutes","team_news_state",
                            "team_news_availability_cap","team_news_age_days",
                            "team_news_source","team_news_carried_forward"]].copy()
        pred["relative_p_start"]=p_rel[test];pred["team_news_p_start"]=p_news[test]
        pred["relative_xmins"]=x_rel[test];pred["team_news_xmins"]=x_news[test]
        write_gzip_csv(pred,out/"reused_diagnostic_predictions.csv.gz")

    write_json(out/"result.json",result)
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
