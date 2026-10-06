#!/usr/bin/env python3
"""MI v2 signal audit and ablation study.

Purpose:
- explain why tau had no effect,
- separate current-match importance from future rotation pressure,
- compare hierarchy-only vs hierarchy+workload feature families,
- tune only on GW16-21, diagnose on untouched GW22-38.
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
OUT=ROOT/"analysis/results/mm-relative-mi-v2-ablation-20261006-v1"
POLICY="soft_0.5_0.1"
TAUS=(2.0,3.0,4.0,5.0,7.0)

FAMILIES={
 "current_only":["mi2_role_h_fast_current","mi2_role_h_slow_current"],
 "future_hierarchy_only":["mi2_role_h_fast_pressure","mi2_role_h_slow_pressure"],
 "current_plus_future_hierarchy":[
   "mi2_role_h_fast_current","mi2_role_h_slow_current",
   "mi2_role_h_fast_pressure","mi2_role_h_slow_pressure"],
 "future_workload_only":["mi2_work7_pressure","mi2_starts7_pressure"],
 "full":[
   "mi2_role_h_fast_current","mi2_role_h_slow_current",
   "mi2_role_h_fast_pressure","mi2_role_h_slow_pressure",
   "mi2_work7_pressure","mi2_starts7_pressure"],
}

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

def score(frame,mask,p,x):
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

def signal_stats(f,tau):
    rows=[]
    for scope,mask in [
      ("all",np.ones(len(f),dtype=bool)),
      ("dev",f.gw.between(16,21).to_numpy()),
      ("holdout",f.gw.between(22,38).to_numpy()),
    ]:
        z=f.loc[mask]
        p=pd.to_numeric(z.mi2_rotation_pressure,errors="coerce").fillna(0.)
        d=pd.to_numeric(z.mi2_days_to_next,errors="coerce")
        rows.append({
          "tau":tau,"scope":scope,"rows":int(len(z)),
          "positive_pressure_rows":int((p>1e-12).sum()),
          "positive_pressure_share":float((p>1e-12).mean()),
          "pressure_mean":float(p.mean()),"pressure_max":float(p.max()),
          "pressure_p95":float(p.quantile(.95)),
          "days_mean_when_pressure":float(d[p>1e-12].mean()) if (p>1e-12).any() else None,
          "current_share_mean":float(pd.to_numeric(z.mi2_current_share,errors="coerce").mean()),
          "current_share_std":float(pd.to_numeric(z.mi2_current_share,errors="coerce").std()),
          "race_mult_mean":float(pd.to_numeric(z.mi2_pl_race_multiplier,errors="coerce").mean()),
          "race_mult_max":float(pd.to_numeric(z.mi2_pl_race_multiplier,errors="coerce").max()),
        })
    return rows

def ensure_features(f,features):
    for c in features:
        if c not in f:f[c]=0.
        f[c]=pd.to_numeric(f[c],errors="coerce").fillna(0.).astype(float)
    return f

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    frame=build_rating_features(frame,pd.read_csv(RATINGS))
    frame=build_strict_team_news_features(frame,read_split_gzip_jsonl(TEAM_NEWS))
    teams=pd.read_csv(TEAMS); code_to_team={int(r.code):int(r.id) for r in teams.itertuples(index=False)}
    snaps=load_gw_schedule_snapshots(RAW,code_to_team)
    frame["target_kickoff"]=target_kickoffs(frame,snaps)
    known=pd.to_datetime(frame.outcome_known_at,utc=True)

    all_feats=sorted(set(sum(FAMILIES.values(),[])))
    cache={}
    signal=[]
    for tau in TAUS:
        f=ensure_features(add_relative_future_mi_v2(frame,snaps,tau_days=tau),all_feats)
        cache[tau]=f
        signal.extend(signal_stats(f,tau))
    pd.DataFrame(signal).to_csv(OUT/"signal_by_tau.csv",index=False)

    # Verify whether tau actually changes raw future pressure/features.
    base_tau=TAUS[0]; ref=cache[base_tau]
    tau_diff=[]
    for tau in TAUS[1:]:
        f=cache[tau]
        for c in ["mi2_rotation_pressure","mi2_role_h_fast_pressure","mi2_role_h_slow_pressure",
                  "mi2_work7_pressure","mi2_starts7_pressure"]:
            a=pd.to_numeric(ref[c],errors="coerce").fillna(0.).to_numpy()
            b=pd.to_numeric(f[c],errors="coerce").fillna(0.).to_numpy()
            tau_diff.append({
              "tau_a":base_tau,"tau_b":tau,"feature":c,
              "max_abs_diff":float(np.max(np.abs(a-b))),
              "mean_abs_diff":float(np.mean(np.abs(a-b))),
              "changed_rows":int((np.abs(a-b)>1e-12).sum()),
            })
    pd.DataFrame(tau_diff).to_csv(OUT/"tau_feature_differences.csv",index=False)

    dev=frame.gw.between(16,21).to_numpy()
    devcut=pd.to_datetime(frame.loc[dev,"cutoff"],utc=True).min()
    devtrain=(frame.gw.between(6,15)&(known<devcut)).to_numpy()
    _,_,_,_,p0,x0,_,_,_=evaluate_news_variant(frame,devtrain,dev,POLICY)
    base_dev=score(frame,dev,p0,x0)

    dev_rows=[{"family":"baseline","tau":None,**base_dev}]
    eligible=[]
    for family,features in FAMILIES.items():
        for tau in TAUS:
            f=cache[tau]
            _,_,_,_,p,x,_,_,_=evaluate_news_variant(
                f,devtrain,dev,POLICY,extra_base_features=features)
            m=score(f,dev,p,x)
            dev_rows.append({"family":family,"tau":tau,**m})
            ok=(m["start_log_loss"]<base_dev["start_log_loss"]
                and m["xmins_mae"]<=base_dev["xmins_mae"]+.05
                and m["xmins_rmse"]<=base_dev["xmins_rmse"]+.05)
            if ok:eligible.append((family,tau,m))
    devtab=pd.DataFrame(dev_rows);devtab.to_csv(OUT/"development_ablation.csv",index=False)

    if eligible:
        selected_family,selected_tau,selected_dev=min(eligible,key=lambda z:z[2]["start_log_loss"])
        promoted=True
    else:
        candidates=[r for r in dev_rows if r["family"]!="baseline"]
        best=min(candidates,key=lambda r:r["start_log_loss"])
        selected_family,selected_tau=best["family"],float(best["tau"])
        selected_dev=best;promoted=False

    # Holdout diagnostics for every family using its best dev tau, not holdout tuning.
    best_by_family={}
    for family in FAMILIES:
        z=devtab[devtab.family.eq(family)].sort_values("start_log_loss").iloc[0]
        best_by_family[family]=float(z.tau)

    hold_rows=[]
    pred_rows=[]
    for family,features in {"baseline":[] ,**FAMILIES}.items():
        tau=2.0 if family=="baseline" else best_by_family[family]
        f=frame if family=="baseline" else cache[tau]
        ps=[];xs=[];ys=[];ms=[]
        for gw in range(22,39):
            val=frame.gw.eq(gw).to_numpy()
            if not val.any():continue
            cut=pd.to_datetime(frame.loc[val,"cutoff"],utc=True).min()
            tr=((frame.gw<gw)&(known<cut)).to_numpy()
            _,_,_,_,p,x,_,_,_=evaluate_news_variant(
                f,tr,val,POLICY,extra_base_features=features)
            ps.extend(p[val]);xs.extend(x[val]);ys.extend(frame.loc[val,"y"]);ms.extend(frame.loc[val,"minutes"])
            if family in ("baseline",selected_family):
                idx=np.where(val)[0]
                for j,i in enumerate(idx):
                    pred_rows.append({
                      "family":family,"tau":None if family=="baseline" else tau,
                      "gw":gw,"player_uuid":frame.iloc[i].player_uuid,
                      "team_id":int(frame.iloc[i].team_id),"player":frame.iloc[i].player,
                      "p_start":float(p[i]),"xmins":float(x[i]),
                      "actual_start":float(frame.iloc[i].y),"minutes":float(frame.iloc[i].minutes),
                    })
        y=np.asarray(ys,float);m=np.asarray(ms,float);p=np.asarray(ps,float);x=np.asarray(xs,float);eps=1e-12
        hold_rows.append({
          "family":family,"tau":None if family=="baseline" else tau,"rows":len(y),
          "start_brier":float(np.mean((p-y)**2)),
          "start_log_loss":float(-np.mean(y*np.log(np.clip(p,eps,1-eps))+(1-y)*np.log(np.clip(1-p,eps,1-eps)))),
          "xmins_mae":float(np.mean(np.abs(x-m))),
          "xmins_rmse":float(np.sqrt(np.mean((x-m)**2))),
          "xmins_bias":float(np.mean(x-m)),
        })
    hold=pd.DataFrame(hold_rows);hold.to_csv(OUT/"holdout_ablation.csv",index=False)
    pd.DataFrame(pred_rows).to_csv(OUT/"selected_vs_baseline_predictions.csv.gz",index=False,compression="gzip")

    result={
      "classification":"MI v2 signal audit + ablation; dev selection GW16-21, untouched holdout GW22-38",
      "selected_family":selected_family,"selected_tau":selected_tau,
      "development_promoted":promoted,"selected_development":selected_dev,
      "best_tau_by_family":best_by_family,
      "baseline_development":base_dev,
      "holdout":hold_rows,
      "tau_raw_signal_changes":tau_diff,
      "PM_TS_unchanged":True,
    }
    write_json(OUT/"result.json",result)
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
