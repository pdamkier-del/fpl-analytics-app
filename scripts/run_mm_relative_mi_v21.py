#!/usr/bin/env python3
"""MI v2.1: absolute future importance pressure test."""
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
OUT=ROOT/"analysis/results/mm-relative-mi-v21-20261007-v1"
POLICY="soft_0.5_0.1";TAUS=(2.,3.,4.,5.,7.)
CURRENT=["mi2_role_h_fast_current","mi2_role_h_slow_current"]
FUTURE_H=["mi2_role_h_fast_pressure","mi2_role_h_slow_pressure"]
FUTURE_W=["mi2_work7_pressure","mi2_starts7_pressure"]

def target_kickoffs(frame,snaps):
    out=[]
    for r in frame.itertuples(index=False):
        ko=np.nan;s=snaps.get(int(r.gw))
        if s is not None and not s.empty:
            g=s[(s.team_id.eq(int(r.team_id)))&(s.competition.eq("prem"))]
            if len(g):
                a=g[g.kickoff>=pd.Timestamp(r.cutoff)].sort_values("kickoff")
                if len(a):ko=a.iloc[0].kickoff
        out.append(ko)
    return out

def metrics(frame,mask,p,x):
    y=frame.loc[mask,"y"].to_numpy(float);m=frame.loc[mask,"minutes"].to_numpy(float)
    pp=p[mask];xx=x[mask];eps=1e-12
    return {"rows":int(mask.sum()),
      "start_brier":float(np.mean((pp-y)**2)),
      "start_log_loss":float(-np.mean(y*np.log(np.clip(pp,eps,1-eps))+(1-y)*np.log(np.clip(1-pp,eps,1-eps)))),
      "xmins_mae":float(np.mean(np.abs(xx-m))),
      "xmins_rmse":float(np.sqrt(np.mean((xx-m)**2))),
      "xmins_bias":float(np.mean(xx-m))}

def prep():
    f=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    f=add_perf_features(f,build_perf_ledger())
    f=build_rating_features(f,pd.read_csv(RATINGS))
    f=build_strict_team_news_features(f,read_split_gzip_jsonl(TEAM_NEWS))
    teams=pd.read_csv(TEAMS);code={int(r.code):int(r.id) for r in teams.itertuples(index=False)}
    snaps=load_gw_schedule_snapshots(RAW,code)
    f["target_kickoff"]=target_kickoffs(f,snaps)
    return f,snaps

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frame,snaps=prep();known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev=frame.gw.between(16,21).to_numpy()
    cut=pd.to_datetime(frame.loc[dev,"cutoff"],utc=True).min()
    trdev=(frame.gw.between(6,15)&(known<cut)).to_numpy()

    _,_,_,_,pb,xb,_,_,_=evaluate_news_variant(frame,trdev,dev,POLICY)
    base=metrics(frame,dev,pb,xb)

    cached={};signal=[];devrows=[{"variant":"baseline","tau":None,**base}]
    families={
      "current_only":CURRENT,
      "future_only":FUTURE_H+FUTURE_W,
      "current_plus_future_h":CURRENT+FUTURE_H,
      "current_plus_future_all":CURRENT+FUTURE_H+FUTURE_W,
    }
    for tau in TAUS:
        f=add_relative_future_mi_v2(frame,snaps,tau_days=tau)
        for c in sorted(set(sum(families.values(),[]))):
            if c not in f:f[c]=0.
            f[c]=pd.to_numeric(f[c],errors="coerce").fillna(0.).astype(float)
        cached[tau]=f
        p=f.mi2_rotation_pressure.fillna(0.)
        signal.append({"tau":tau,"positive_rows":int((p>1e-12).sum()),
                       "positive_share":float((p>1e-12).mean()),
                       "mean":float(p.mean()),"p95":float(p.quantile(.95)),
                       "max":float(p.max())})
        for name,features in families.items():
            _,_,_,_,ps,xs,_,_,_=evaluate_news_variant(f,trdev,dev,POLICY,extra_base_features=features)
            devrows.append({"variant":name,"tau":tau,**metrics(f,dev,ps,xs)})
    pd.DataFrame(signal).to_csv(OUT/"signal_by_tau.csv",index=False)
    devtab=pd.DataFrame(devrows);devtab.to_csv(OUT/"development.csv",index=False)

    # choose per family on dev; diagnostic all families on holdout using chosen tau
    best={}
    for name in families:
        z=devtab[devtab.variant.eq(name)].sort_values("start_log_loss").iloc[0]
        best[name]=float(z.tau)

    hold=[]
    for name,features in {"baseline":[],**families}.items():
        f=frame if name=="baseline" else cached[best[name]]
        ps=[];xs=[];ys=[];ms=[]
        for gw in range(22,39):
            val=frame.gw.eq(gw).to_numpy()
            if not val.any():continue
            c=pd.to_datetime(frame.loc[val,"cutoff"],utc=True).min()
            tr=((frame.gw<gw)&(known<c)).to_numpy()
            _,_,_,_,p,x,_,_,_=evaluate_news_variant(f,tr,val,POLICY,extra_base_features=features)
            ps.extend(p[val]);xs.extend(x[val]);ys.extend(frame.loc[val,"y"]);ms.extend(frame.loc[val,"minutes"])
        y=np.asarray(ys,float);m=np.asarray(ms,float);p=np.asarray(ps,float);x=np.asarray(xs,float);eps=1e-12
        hold.append({"variant":name,"tau":None if name=="baseline" else best[name],"rows":len(y),
          "start_brier":float(np.mean((p-y)**2)),
          "start_log_loss":float(-np.mean(y*np.log(np.clip(p,eps,1-eps))+(1-y)*np.log(np.clip(1-p,eps,1-eps)))),
          "xmins_mae":float(np.mean(np.abs(x-m))),
          "xmins_rmse":float(np.sqrt(np.mean((x-m)**2))),
          "xmins_bias":float(np.mean(x-m))})
    pd.DataFrame(hold).to_csv(OUT/"holdout.csv",index=False)

    result={"classification":"MI v2.1 absolute future pressure",
            "baseline_dev":base,"best_tau_by_family":best,
            "development":devrows,"signal":signal,"holdout":hold,
            "PM_TS_unchanged":True}
    write_json(OUT/"result.json",result);print(json.dumps(result,indent=2))

if __name__=="__main__":main()
