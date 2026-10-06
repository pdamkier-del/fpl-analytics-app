#!/usr/bin/env python3
"""Sequential MM structural promotion pipeline.

M0 Team News reference.
Each next family is added to the latest promoted set and gated on GW16-21 only.
All candidates are then replayed walk-forward on GW22-38 for diagnostics.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"scripts"))

from fpl_v1_1_model.future_match_importance import load_gw_schedule_snapshots,add_forward_match_importance
from fpl_v1_1_model.structural_context import StructuralHistory,add_structural_context
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
CLASSIFIED=ROOT/"analysis/results/reproducible-role-v1/classified_starters.csv"
OFFICIAL=ROOT/"analysis/results/workload-recovered-v4/official_player_minutes.csv"
COVERAGE=ROOT/"analysis/results/workload-recovered-v4/team_match_coverage.csv"
OUT=ROOT/"analysis/results/mm-structural-promotion-20261006-v1"
POLICY="soft_0.5_0.1"

FUTURE=[
 "future_role_h_fast_pressure","future_role_h_slow_pressure",
 "future_work7_pressure","future_starts7_pressure",
 "future_next_is_europe","future_next_is_fa_cup","future_next_is_efl_cup",
]
FORMATION=[
 "form_cond_start_prior","form_role_concentration","form_role_evidence","form_expected_seen",
]
COLD=[
 "cold_role_low_evidence","cold_work_starts14","cold_work_minutes14",
]
ROTATION=[
 "rot_pl_start_share","rot_nonpl_start_share","rot_europe_start_share",
 "rot_cup_start_share","rot_pl_minus_nonpl","rot_evidence",
]
GK=[
 "gk_pl_streak","gk_other_keeper_hard_out","gk_unexplained_change_signal",
]
REGIME=[
 "team_regime_shift","regime_h_slow_interaction","regime_h_fast_interaction",
]
FAMILIES=[
 ("future_match_importance",FUTURE),
 ("formation_conditioned_qh",FORMATION),
 ("cold_start_prior",COLD),
 ("competition_rotation",ROTATION),
 ("conditional_gk_change",GK),
 ("lineup_regime_decay",REGIME),
]

def metrics_row(frame,mask,p,x):
    y=frame.loc[mask,"y"].to_numpy(float);m=frame.loc[mask,"minutes"].to_numpy(float)
    pp=p[mask];xx=x[mask]
    return {
      "rows":int(mask.sum()),
      "start_brier":float(np.mean((pp-y)**2)),
      "start_log_loss":float(-np.mean(y*np.log(np.clip(pp,1e-12,1-1e-12))+(1-y)*np.log(np.clip(1-pp,1e-12,1-1e-12)))),
      "xmins_mae":float(np.mean(np.abs(xx-m))),
      "xmins_rmse":float(np.sqrt(np.mean((xx-m)**2))),
    }

def eval_once(frame,train,val,features):
    feat,_,_,_,p,x,_,_,met=evaluate_news_variant(frame,train,val,POLICY,extra_base_features=features)
    return feat,p,x,met

def passes(candidate,reference):
    return (
      candidate["state_log_loss"] < reference["state_log_loss"] and
      candidate["xmins_mae"] <= reference["xmins_mae"] + .05 and
      candidate["xmins_rmse"] <= reference["xmins_rmse"] + .05
    )

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    frame=build_rating_features(frame,pd.read_csv(RATINGS))
    frame=build_strict_team_news_features(frame,read_split_gzip_jsonl(TEAM_NEWS))

    teams=pd.read_csv(TEAMS);code_to_team={int(r.code):int(r.id) for r in teams.itertuples(index=False)}
    snaps=load_gw_schedule_snapshots(RAW,code_to_team)
    target_ko=[]
    for r in frame.itertuples(index=False):
        sched=snaps.get(int(r.gw));ko=np.nan
        if sched is not None and not sched.empty:
            g=sched[(sched.team_id.eq(int(r.team_id)))&(sched.competition.eq("prem"))]
            if len(g):
                aft=g[g.kickoff>=pd.Timestamp(r.cutoff)].sort_values("kickoff")
                if len(aft):ko=aft.iloc[0].kickoff
        target_ko.append(ko)
    frame["target_kickoff"]=target_ko
    frame=add_forward_match_importance(frame,snaps,tau_days=4.0)

    history=StructuralHistory(pd.read_csv(CLASSIFIED),pd.read_csv(OFFICIAL),pd.read_csv(COVERAGE))
    frame=add_structural_context(frame,history)

    all_features=sum((v for _,v in FAMILIES),[])
    for c in all_features:
        if c not in frame:frame[c]=0.
        frame[c]=pd.to_numeric(frame[c],errors="coerce").fillna(0.).astype(float)

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev=frame.gw.between(16,21).to_numpy()
    devcut=pd.to_datetime(frame.loc[dev,"cutoff"],utc=True).min()
    devtrain=(frame.gw.between(6,15)&(known<devcut)).to_numpy()

    promoted=[]
    feat,p,x,base=eval_once(frame,devtrain,dev,promoted)
    decisions=[{"stage":"M0_team_news","features":[],"promoted":True,"development":base}]
    current=base

    for name,family in FAMILIES:
        cand_features=promoted+family
        _,_,_,cand=eval_once(frame,devtrain,dev,cand_features)
        ok=passes(cand,current)
        decisions.append({
          "stage":name,"candidate_features":cand_features,"added":family,
          "promoted":bool(ok),"development":cand,
          "delta_vs_current":{k:float(cand[k]-current[k]) for k in
                              ("state_log_loss","state_brier","xmins_mae","xmins_rmse")}
        })
        if ok:
            promoted=cand_features
            current=cand

    # Diagnostic walk-forward on every cumulative candidate as proposed and on final promoted model.
    variants={"M0_team_news":[]}
    cumulative=[]
    for name,family in FAMILIES:
        cumulative=cumulative+family
        variants[name]=list(cumulative)
    variants["FINAL_PROMOTED"]=list(promoted)

    diag_rows=[];gk_rows=[];shock_rows=[]
    for label,features in variants.items():
        for gw in range(22,39):
            val=frame.gw.eq(gw).to_numpy()
            if not val.any():continue
            cut=pd.to_datetime(frame.loc[val,"cutoff"],utc=True).min()
            tr=((frame.gw<gw)&(known<cut)).to_numpy()
            feat,p,x,met=eval_once(frame,tr,val,features)
            rec={"variant":label,"gw":gw,**{k:float(met[k]) for k in
                 ("state_log_loss","state_brier","xmins_mae","xmins_rmse","xmins_bias")}}
            diag_rows.append(rec)

            pos=frame.pos.astype(str).str.upper().isin(["G","GK"]).to_numpy()
            gm=val&pos
            if gm.any():
                g=metrics_row(frame,gm,p,x);g.update({"variant":label,"gw":gw});gk_rows.append(g)

            if label=="FINAL_PROMOTED":
                y=frame.y.to_numpy(float);mins=frame.minutes.to_numpy(float)
                idx=np.where(val&((np.abs(x-mins)>=60)|((p>=.8)&(y<.5))|((p<=.2)&(y>=.5))))[0]
                for i in idx:
                    shock_rows.append({
                      "gw":gw,"team":frame.iloc[i].team,"player":frame.iloc[i].player,
                      "pos":frame.iloc[i].pos,"p_start":float(p[i]),"xmins":float(x[i]),
                      "actual_start":float(y[i]),"minutes":float(mins[i]),
                      "abs_min_error":float(abs(x[i]-mins[i])),
                      "team_news_state":frame.iloc[i].team_news_state,
                      "future_pressure":float(frame.iloc[i].future_rotation_pressure),
                      "gk_change_signal":float(frame.iloc[i].gk_unexplained_change_signal),
                      "regime_shift":float(frame.iloc[i].team_regime_shift),
                    })

    pd.DataFrame(decisions).to_json(OUT/"development_decisions.json",orient="records",indent=2)
    diag=pd.DataFrame(diag_rows);diag.to_csv(OUT/"diagnostic_by_gw.csv",index=False)
    gk=pd.DataFrame(gk_rows);gk.to_csv(OUT/"goalkeeper_by_gw.csv",index=False)
    pd.DataFrame(shock_rows).to_csv(OUT/"final_major_shocks.csv",index=False)

    def aggregate(tab,label):
        z=tab[tab.variant.eq(label)]
        return {
          "gws":int(z.gw.nunique()),
          "state_log_loss_mean":float(z.state_log_loss.mean()) if "state_log_loss" in z else None,
          "state_brier_mean":float(z.state_brier.mean()) if "state_brier" in z else None,
          "xmins_mae_mean":float(z.xmins_mae.mean()),
          "xmins_rmse_mean":float(z.xmins_rmse.mean()),
        }
    result={
      "classification":"sequential structural MM promotion pipeline",
      "policy":POLICY,
      "development_gate":"promote iff log-loss improves and MAE/RMSE worsen by <=0.05",
      "decisions":decisions,
      "final_promoted_features":promoted,
      "diagnostic_summary":{k:aggregate(diag,k) for k in variants},
      "goalkeeper_summary":{k:aggregate(gk,k) for k in variants},
      "PM_TS_unchanged":True,
    }
    write_json(OUT/"result.json",result)
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
