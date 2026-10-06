#!/usr/bin/env python3
"""A/B walk-forward: Team News MM vs Team News MM + forward Match Importance."""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"scripts"))

from fpl_v1_1_model.future_match_importance import load_gw_schedule_snapshots,add_forward_match_importance
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
OUT=ROOT/"analysis/results/mm-future-mi-walkforward-20261006-v1"
POLICY="soft_0.5_0.1"
FEATURES=[
  "future_role_h_fast_pressure","future_role_h_slow_pressure",
  "future_work7_pressure","future_starts7_pressure",
  "future_next_is_europe","future_next_is_fa_cup","future_next_is_efl_cup",
]

def calc(part,p,x):
    y=part.y.to_numpy(float);m=part.minutes.to_numpy(float)
    return {
      "rows":int(len(part)),
      "start_brier":float(np.mean((p-y)**2)),
      "start_log_loss":float(-np.mean(y*np.log(np.clip(p,1e-12,1-1e-12))+(1-y)*np.log(np.clip(1-p,1e-12,1-1e-12)))),
      "xmins_mae":float(np.mean(np.abs(x-m))),
      "xmins_rmse":float(np.sqrt(np.mean((x-m)**2))),
      "xmins_bias":float(np.mean(x-m)),
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    frame=build_rating_features(frame,pd.read_csv(RATINGS))
    strict=read_split_gzip_jsonl(TEAM_NEWS,"predeadline_strict.jsonl.gz")
    frame=build_strict_team_news_features(frame,strict)

    teams=pd.read_csv(TEAMS)
    code_to_team={int(r.code):int(r.id) for r in teams.itertuples(index=False)}
    snaps=load_gw_schedule_snapshots(RAW,code_to_team)

    # Anchor with known target kickoff from fixture rows in each snapshot.
    target_ko=[]
    for r in frame.itertuples(index=False):
        sched=snaps.get(int(r.gw))
        ko=np.nan
        if sched is not None and not sched.empty:
            g=sched[(sched.team_id.eq(int(r.team_id)))&(sched.competition.eq("prem"))]
            if len(g):
                cut=pd.Timestamp(r.cutoff)
                aft=g[g.kickoff>=cut].sort_values("kickoff")
                if len(aft): ko=aft.iloc[0].kickoff
        target_ko.append(ko)
    frame["target_kickoff"]=target_ko
    frame=add_forward_match_importance(frame,snaps,tau_days=4.0)

    for c in FEATURES:
        if c not in frame: frame[c]=0.
        if frame[c].dtype==object: frame[c]=pd.to_numeric(frame[c],errors="coerce")
        frame[c]=frame[c].fillna(0.).astype(float)

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    rows=[];preds=[]
    for gw in sorted(int(g) for g in frame.gw.unique() if int(g)>=11):
        val=frame.gw.eq(gw).to_numpy()
        cutoff=pd.to_datetime(frame.loc[val,"cutoff"],utc=True).min()
        train=((frame.gw<gw)&(known<cutoff)).to_numpy()
        if frame.loc[train,"gw"].nunique()<5: continue

        b=evaluate_news_variant(frame,train,val,POLICY)
        f=evaluate_news_variant(frame,train,val,POLICY,extra_base_features=FEATURES)
        feat,_,_,_,pb,xb,_,_,mb=b
        _,_,_,_,pf,xf,_,_,mf=f

        rec={"gw":gw}
        for k in ("state_log_loss","state_brier","xmins_mae","xmins_rmse","xmins_bias"):
            rec["base_"+k]=float(mb[k]);rec["future_"+k]=float(mf[k]);rec["delta_"+k]=float(mf[k]-mb[k])
        rows.append(rec)

        part=feat.loc[val,["gw","team","team_id","player","player_uuid","pos","y","minutes","team_news_state"]].copy()
        part["base_p_start"]=pb[val];part["future_p_start"]=pf[val]
        part["base_xmins"]=xb[val];part["future_xmins"]=xf[val]
        part["future_rotation_pressure"]=frame.loc[val,"future_rotation_pressure"].to_numpy(float)
        part["future_days_to_next"]=frame.loc[val,"future_days_to_next"].to_numpy()
        part["future_next_competition"]=frame.loc[val,"future_next_competition"].to_numpy()
        preds.append(part)

    pred=pd.concat(preds,ignore_index=True)
    pd.DataFrame(rows).to_csv(OUT/"by_gw.csv",index=False)
    pred.to_csv(OUT/"predictions.csv.gz",index=False,compression="gzip")

    y=pred.y.to_numpy(float)
    base=calc(pred,pred.base_p_start.to_numpy(float),pred.base_xmins.to_numpy(float))
    fut=calc(pred,pred.future_p_start.to_numpy(float),pred.future_xmins.to_numpy(float))
    gk=pred[pred.pos.astype(str).str.upper().eq("G")|pred.pos.astype(str).str.upper().eq("GK")]
    gb=calc(gk,gk.base_p_start.to_numpy(float),gk.base_xmins.to_numpy(float))
    gf=calc(gk,gk.future_p_start.to_numpy(float),gk.future_xmins.to_numpy(float))
    summary={
      "classification":"A/B walk-forward Team News MM vs future Match Importance",
      "gws":[11,38],"policy":POLICY,
      "features":FEATURES,
      "all":{"base":base,"future_mi":fut,"delta":{k:fut[k]-base[k] for k in fut if k!="rows"}},
      "goalkeepers":{"base":gb,"future_mi":gf,"delta":{k:gf[k]-gb[k] for k in gf if k!="rows"}},
      "future_context_coverage":{
        "rows_with_next_match":int(pred.future_days_to_next.notna().sum()),
        "rows_with_positive_pressure":int((pred.future_rotation_pressure>0).sum()),
      }
    }
    write_json(OUT/"summary.json",summary)
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
