#!/usr/bin/env python3
"""Walk-forward 2025/26 Minute Model season replay.

Feature universe begins at GW6. GWs 6-10 are warm-up; GWs 11-38 are scored.
The selected Team News policy (soft_0.5_0.1) was chosen on GW16-21, so:
- GW11-21 is retrospective/pre-selection replay;
- GW22-38 is post-selection walk-forward diagnostic.

Every target GW is refit using only outcomes known before that GW cutoff.
PM/TS are untouched.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"scripts"))

from fpl_v1_1_model.rating_history import build_rating_features
from fpl_v1_1_model.team_news_history import read_split_gzip_jsonl,build_strict_team_news_features
from run_mm_unified_official_roles import SOURCE
from run_v4_performance_rating_experiment import build_perf_ledger,add_features as add_perf_features
from run_v4_three_state_sequence_experiment import add_sequence_features,metrics,write_gzip_csv,write_json
from run_mm_v2_team_news_availability_experiment import evaluate_news_variant
from run_mm_v2_relative_rating_competition import evaluate_variant
RATING_CFG={"name":"relative_self_trend","gamma":.02,"rel_w":.65,"self_w":.25,"trend_w":.10}

RATINGS=ROOT/"data_v1_1/derived/mm_v2_ratings/player_match_ratings.csv.gz"
TEAM_NEWS=ROOT/"data_v1_1/derived/team_news_audit/2025-26-v2"
OUT=ROOT/"analysis/results/mm-team-news-season-walkforward-20261006-v1"
POLICY="soft_0.5_0.1"
L2=.5
FIRST_SCORE_GW=11

def safe_float(v):
    try:return float(v)
    except:return None

def aggregate_metrics(out):
    y=out.actual_start.to_numpy(float);p=out.team_news_p_start.to_numpy(float)
    xm=out.team_news_xmins.to_numpy(float);mins=out.minutes.to_numpy(float)
    eps=1e-12
    return {
        "rows":int(len(out)),
        "start_brier":float(np.mean((p-y)**2)),
        "start_log_loss":float(-np.mean(y*np.log(np.clip(p,eps,1-eps))+(1-y)*np.log(np.clip(1-p,eps,1-eps)))),
        "start_mae":float(np.mean(np.abs(p-y))),
        "xmins_mae":float(np.mean(np.abs(xm-mins))),
        "xmins_rmse":float(np.sqrt(np.mean((xm-mins)**2))),
        "xmins_bias":float(np.mean(xm-mins)),
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    frame=build_rating_features(frame,pd.read_csv(RATINGS))
    strict=read_split_gzip_jsonl(TEAM_NEWS,"predeadline_strict.jsonl.gz")
    frame=build_strict_team_news_features(frame,strict)

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    gws=sorted(int(g) for g in frame.gw.unique() if int(g)>=FIRST_SCORE_GW)
    all_rows=[];gw_summaries=[]

    for gw in gws:
        target=frame.gw.eq(gw).to_numpy()
        cutoff=pd.to_datetime(frame.loc[target,"cutoff"],utc=True).min()
        train=((frame.gw<gw)&(known<cutoff)).to_numpy()
        train_gws=sorted(int(g) for g in frame.loc[train,"gw"].unique())
        if len(train_gws)<5:
            continue

        # Reference and selected Team News model are both refit for this target GW.
        _,_,_,_,_,_,ref_rows,_,ref_preds=evaluate_variant(
            frame,train,target,RATING_CFG,l2s=(L2,))
        ref_met=ref_rows.iloc[0].to_dict()
        ref_p,ref_x=ref_preds[L2]

        feat,p_locked,x_locked,p_pre,p_news,x_news,q,sub,tn_met=evaluate_news_variant(
            frame,train,target,POLICY)

        cols=["fixture_uuid","player_uuid","team_id","gw","team","player","pos",
              "expected_role","xi_assigned_role","xi_formation","y","minutes",
              "team_news_state","team_news_scoped_chance","team_news_availability_cap",
              "team_news_age_hours"]
        part=feat.loc[target,cols].copy()
        part["actual_start"]=part.y.astype(float)
        part["reference_p_start"]=ref_p[target]
        part["reference_xmins"]=ref_x[target]
        part["locked_p_start"]=p_locked[target]
        part["locked_xmins"]=x_locked[target]
        part["pre_xi_availability_p_start"]=p_pre[target]
        part["team_news_p_start"]=p_news[target]
        part["team_news_xmins"]=x_news[target]
        part["start_abs_error"]=(part.team_news_p_start-part.actual_start).abs()
        part["minute_error"]=part.team_news_xmins-part.minutes
        part["minute_abs_error"]=part.minute_error.abs()
        part["reference_minute_abs_error"]=(part.reference_xmins-part.minutes).abs()
        part["team_news_gain_abs_minutes"]=part.reference_minute_abs_error-part.minute_abs_error

        # Independent flags: one row can legitimately have multiple error types.
        part["flag_high_pstart_nonstart"]=(part.team_news_p_start.ge(.8)&part.actual_start.lt(.5))
        part["flag_low_pstart_started"]=(part.team_news_p_start.le(.2)&part.actual_start.ge(.5))
        part["flag_map_false_positive"]=(feat.loc[target,"xi_selected_map"].to_numpy()>=.5)&part.actual_start.lt(.5)
        part["flag_map_false_negative"]=(feat.loc[target,"xi_selected_map"].to_numpy()<.5)&part.actual_start.ge(.5)
        part["flag_minute_error_30plus"]=part.minute_abs_error.ge(30)
        part["flag_minute_error_45plus"]=part.minute_abs_error.ge(45)
        part["flag_minute_error_60plus"]=part.minute_abs_error.ge(60)
        part["evaluation_tier"]=np.where(gw<=21,"preselection_replay","postselection_walkforward")
        all_rows.append(part)

        rec={"gw":gw,"train_gw_min":min(train_gws),"train_gw_max":max(train_gws),
             "train_gw_count":len(train_gws),"rows":int(target.sum()),
             "evaluation_tier":"preselection_replay" if gw<=21 else "postselection_walkforward"}
        for k in ["state_log_loss","state_brier","xmins_mae","xmins_rmse","xmins_bias"]:
            rec["reference_"+k]=safe_float(ref_met.get(k))
            rec["team_news_"+k]=safe_float(tn_met.get(k))
            if rec["reference_"+k] is not None and rec["team_news_"+k] is not None:
                rec["delta_"+k]=rec["team_news_"+k]-rec["reference_"+k]
        gw_summaries.append(rec)
        print("GW",gw,"train",train_gws[0],"-",train_gws[-1],
              "MAE",round(tn_met["xmins_mae"],4),
              "delta",round(tn_met["xmins_mae"]-ref_met["xmins_mae"],4),flush=True)

    out=pd.concat(all_rows,ignore_index=True).sort_values(["gw","team","player"])
    write_gzip_csv(out,OUT/"all_player_gw_predictions.csv.gz")
    pd.DataFrame(gw_summaries).to_csv(OUT/"by_gw.csv",index=False)

    def grouped(keys,name):
        z=out.groupby(keys,dropna=False).agg(
            rows=("player_uuid","size"),
            actual_starts=("actual_start","sum"),
            start_mae=("start_abs_error","mean"),
            xmins_mae=("minute_abs_error","mean"),
            reference_xmins_mae=("reference_minute_abs_error","mean"),
            mean_team_news_gain=("team_news_gain_abs_minutes","mean"),
            high_p_nonstart=("flag_high_pstart_nonstart","sum"),
            low_p_started=("flag_low_pstart_started","sum"),
            map_false_positive=("flag_map_false_positive","sum"),
            map_false_negative=("flag_map_false_negative","sum"),
            minute_error_30plus=("flag_minute_error_30plus","sum"),
            minute_error_45plus=("flag_minute_error_45plus","sum"),
            minute_error_60plus=("flag_minute_error_60plus","sum"),
        ).reset_index().sort_values("xmins_mae",ascending=False)
        z.to_csv(OUT/name,index=False)

    grouped(["team"],"by_team.csv")
    grouped(["expected_role"],"by_role.csv")
    grouped(["team_news_state"],"by_team_news_state.csv")
    grouped(["team","player_uuid","player","pos"],"by_player.csv")

    worst=out.sort_values(["minute_abs_error","start_abs_error"],ascending=False).head(1000)
    worst.to_csv(OUT/"worst_player_gw_errors.csv",index=False)
    shocks=out[(out.flag_high_pstart_nonstart)|(out.flag_low_pstart_started)|(out.flag_minute_error_60plus)]
    shocks.sort_values(["gw","team","minute_abs_error"],ascending=[True,True,False]).to_csv(
        OUT/"major_lineup_shocks.csv",index=False)

    summary={
        "classification":"2025/26 MM Team News expanding walk-forward season replay",
        "policy":POLICY,
        "feature_universe_gws":[int(frame.gw.min()),int(frame.gw.max())],
        "warmup_gws":[6,7,8,9,10],
        "scored_gws":gws,
        "methodology":{
            "weekly_refit":True,
            "target_gw_excluded_from_training":True,
            "outcome_known_before_cutoff_only":True,
            "strict_team_news_only":True,
            "gw11_21_label":"retrospective/pre-selection replay because Team News policy was later selected on GW16-21",
            "gw22_38_label":"post-selection walk-forward diagnostic",
            "PM_TS_unchanged":True,
        },
        "all_scored":aggregate_metrics(out),
        "preselection_replay":aggregate_metrics(out[out.gw<=21]),
        "postselection_walkforward":aggregate_metrics(out[out.gw>=22]),
        "error_counts":{
            "high_pstart_nonstart":int(out.flag_high_pstart_nonstart.sum()),
            "low_pstart_started":int(out.flag_low_pstart_started.sum()),
            "map_false_positive":int(out.flag_map_false_positive.sum()),
            "map_false_negative":int(out.flag_map_false_negative.sum()),
            "minute_error_30plus":int(out.flag_minute_error_30plus.sum()),
            "minute_error_45plus":int(out.flag_minute_error_45plus.sum()),
            "minute_error_60plus":int(out.flag_minute_error_60plus.sum()),
        },
        "reference_comparison":{
            "reference_xmins_mae":float(out.reference_minute_abs_error.mean()),
            "team_news_xmins_mae":float(out.minute_abs_error.mean()),
            "delta_mae":float(out.minute_abs_error.mean()-out.reference_minute_abs_error.mean()),
        }
    }
    write_json(OUT/"summary.json",summary)
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
