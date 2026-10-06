#!/usr/bin/env python3
"""A/B test Team News MM vs relative Match Importance v2.

Tune tau only on GW16-21. Evaluate selected tau walk-forward on untouched GW22-38.
No PM/TS changes.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"scripts"))

from fpl_v1_1_model.future_match_importance import load_gw_schedule_snapshots
from fpl_v1_1_model.relative_future_match_importance import add_relative_future_mi_v2
from fpl_v1_1_model.rating_history import build_rating_features
from fpl_v1_1_model.team_news_history import read_split_gzip_jsonl,build_strict_team_news_features
from run_mm_unified_official_roles import SOURCE
from run_v4_performance_rating_experiment import build_perf_ledger,add_features as add_perf_features
from run_v4_three_state_sequence_experiment import add_sequence_features,write_json
from run_mm_v2_team_news_availability_experiment import evaluate_news_variant

RATINGS=ROOT/"data_v1_1/derived/mm_v2_ratings/player_match_ratings.csv.gz"
TEAM_NEWS=ROOT/"data_v1_1/derived/team_news_audit/2025-26-v2"
TEAMS=ROOT/"data_v1_1/derived/mm_v2_ratings/identity_source/data/2025-2026/teams.csv"
RAW=ROOT/"data_v1_1/raw/all-competitions-2025-26"
OUT=ROOT/"analysis/results/mm-relative-mi-v2-20261006-v1"
POLICY="soft_0.5_0.1"
TAUS=(2.0,3.0,4.0,5.0,7.0)
FEATURES=[
 "mi2_role_h_fast_current","mi2_role_h_slow_current",
 "mi2_role_h_fast_pressure","mi2_role_h_slow_pressure",
 "mi2_work7_pressure","mi2_starts7_pressure",
]

def target_kickoffs(frame,snaps):
    vals=[]
    for r in frame.itertuples(index=False):
        sched=snaps.get(int(r.gw));ko=np.nan
        if sched is not None and not sched.empty:
            g=sched[(sched.team_id.eq(int(r.team_id)))&(sched.competition.eq("prem"))]
            if len(g):
                aft=g[g.kickoff>=pd.Timestamp(r.cutoff)].sort_values("kickoff")
                if len(aft):ko=aft.iloc[0].kickoff
        vals.append(ko)
    return vals

def metrics(frame,mask,p,x):
    y=frame.loc[mask,"y"].to_numpy(float);m=frame.loc[mask,"minutes"].to_numpy(float)
    pp=p[mask];xx=x[mask];eps=1e-12
    return {
      "rows":int(mask.sum()),
      "start_brier":float(np.mean((pp-y)**2)),
      "start_log_loss":float(-np.mean(y*np.log(np.clip(pp,eps,1-eps))+(1-y)*np.log(np.clip(1-pp,eps,1-eps)))),
      "xmins_mae":float(np.mean(np.abs(xx-m))),
      "xmins_rmse":float(np.sqrt(np.mean((xx-m)**2))),
      "xmins_bias":float(np.mean(xx-m)),
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    frame=build_rating_features(frame,pd.read_csv(RATINGS))
    frame=build_strict_team_news_features(frame,read_split_gzip_jsonl(TEAM_NEWS))

    teams=pd.read_csv(TEAMS)
    code_to_team={int(r.code):int(r.id) for r in teams.itertuples(index=False)}
    snaps=load_gw_schedule_snapshots(RAW,code_to_team)
    frame["target_kickoff"]=target_kickoffs(frame,snaps)
    known=pd.to_datetime(frame.outcome_known_at,utc=True)

    dev=frame.gw.between(16,21).to_numpy()
    devcut=pd.to_datetime(frame.loc[dev,"cutoff"],utc=True).min()
    devtrain=(frame.gw.between(6,15)&(known<devcut)).to_numpy()

    # Baseline reference.
    _,_,_,_,bp,bx,_,_,bmet=evaluate_news_variant(frame,devtrain,dev,POLICY)
    dev_rows=[{"variant":"M0_team_news","tau":None,**metrics(frame,dev,bp,bx)}]

    candidates=[]
    cached={}
    for tau in TAUS:
        f=add_relative_future_mi_v2(frame,snaps,tau_days=tau)
        for c in FEATURES:
            if c not in f:f[c]=0.
            f[c]=pd.to_numeric(f[c],errors="coerce").fillna(0.).astype(float)
        _,_,_,_,p,x,_,_,met=evaluate_news_variant(
            f,devtrain,dev,POLICY,extra_base_features=FEATURES)
        mm=metrics(f,dev,p,x)
        dev_rows.append({"variant":"MI_v2","tau":tau,**mm})
        candidates.append((tau,mm))
        cached[tau]=f

    # Select only on development. Require better log-loss and no meaningful
    # degradation in minute errors vs M0.
    base=dev_rows[0]
    eligible=[(tau,m) for tau,m in candidates
              if m["start_log_loss"]<base["start_log_loss"]
              and m["xmins_mae"]<=base["xmins_mae"]+.05
              and m["xmins_rmse"]<=base["xmins_rmse"]+.05]
    if eligible:
        selected_tau,minmet=min(eligible,key=lambda z:z[1]["start_log_loss"])
        promoted=True
    else:
        selected_tau,minmet=min(candidates,key=lambda z:z[1]["start_log_loss"])
        promoted=False

    fsel=cached[selected_tau]
    # Untouched holdout: weekly refit GW22-38.
    pred_rows=[]
    for gw in range(22,39):
        val=frame.gw.eq(gw).to_numpy()
        if not val.any():continue
        cut=pd.to_datetime(frame.loc[val,"cutoff"],utc=True).min()
        tr=((frame.gw<gw)&(known<cut)).to_numpy()

        _,_,_,_,p0,x0,_,_,_=evaluate_news_variant(frame,tr,val,POLICY)
        _,_,_,_,p1,x1,_,_,_=evaluate_news_variant(
            fsel,tr,val,POLICY,extra_base_features=FEATURES)

        idx=np.where(val)[0]
        for i in idx:
            pred_rows.append({
              "gw":gw,"player_uuid":frame.iloc[i].player_uuid,"team_id":int(frame.iloc[i].team_id),
              "player":frame.iloc[i].player,"team":frame.iloc[i].team,"pos":frame.iloc[i].pos,
              "y":float(frame.iloc[i].y),"minutes":float(frame.iloc[i].minutes),
              "baseline_p_start":float(p0[i]),"baseline_xmins":float(x0[i]),
              "mi2_p_start":float(p1[i]),"mi2_xmins":float(x1[i]),
              "mi2_current_share":float(fsel.iloc[i].mi2_current_share),
              "mi2_next_share":float(fsel.iloc[i].mi2_next_share),
              "mi2_rotation_pressure":float(fsel.iloc[i].mi2_rotation_pressure),
              "mi2_pl_race_multiplier":float(fsel.iloc[i].mi2_pl_race_multiplier),
              "mi2_next_competition":fsel.iloc[i].mi2_next_competition,
              "mi2_next_stage":fsel.iloc[i].mi2_next_stage,
            })
        print("GW",gw,"done",flush=True)

    pred=pd.DataFrame(pred_rows)
    pred.to_csv(OUT/"holdout_predictions.csv.gz",index=False,compression="gzip")

    def pred_metrics(prefix):
        y=pred.y.to_numpy(float);m=pred.minutes.to_numpy(float)
        p=pred[f"{prefix}_p_start"].to_numpy(float);x=pred[f"{prefix}_xmins"].to_numpy(float)
        eps=1e-12
        return {
          "rows":int(len(pred)),
          "start_brier":float(np.mean((p-y)**2)),
          "start_log_loss":float(-np.mean(y*np.log(np.clip(p,eps,1-eps))+(1-y)*np.log(np.clip(1-p,eps,1-eps)))),
          "xmins_mae":float(np.mean(np.abs(x-m))),
          "xmins_rmse":float(np.sqrt(np.mean((x-m)**2))),
          "xmins_bias":float(np.mean(x-m)),
        }

    bm=pred_metrics("baseline");mm=pred_metrics("mi2")
    result={
      "classification":"relative MI v2 A/B; tau selected on GW16-21 only",
      "policy":POLICY,
      "features":FEATURES,
      "tau_grid":list(TAUS),
      "development":dev_rows,
      "selected_tau":selected_tau,
      "development_promoted":promoted,
      "holdout_gws":[22,38],
      "holdout_baseline":bm,
      "holdout_mi2":mm,
      "holdout_delta":{k:mm[k]-bm[k] for k in bm if k!="rows"},
      "PM_TS_unchanged":True,
      "notes":[
        "PL table reconstructed from finished PL matches before each target cutoff.",
        "Competition shares use a fixed normalized budget summing to one.",
        "Cup stage is inferred from the 2025/26 competition calendar without using future results.",
        "Only fixtures present in the target GW schedule snapshot are used as future context."
      ],
    }
    pd.DataFrame(dev_rows).to_csv(OUT/"development_tau_grid.csv",index=False)
    write_json(OUT/"result.json",result)
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
