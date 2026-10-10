#!/usr/bin/env python3
"""Reproduce frozen 2023-25-trained P(start) v2 baseline for current GW.

Exactly reuses stored coefficients (analysis/results/v2-reproduced/metrics.json)
and project_minutes from the historical reproduction. This is the base input
to the frozen subsequent MM, not the entire locked MM inference.
No future outcomes, new hyperparameters, refitting or FPL ep_next.
"""
from __future__ import annotations
import ast,json,sys
from pathlib import Path
from collections import defaultdict
import numpy as np,pandas as pd
from scipy.special import expit,logit

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"scripts")]
from fpl_v1_1_model.minutes import project_minutes
from build_reproducible_role_benchmark import normalize_eleven

BASE=ROOT/"data_v1_1/derived/live_locked_inputs/2026-27-v1"
INPUT=BASE/"performance_feature_matrix.csv.gz"
HISTORY=BASE/"player_fixture_observations.csv.gz"
COEFS=ROOT/"analysis/results/v2-reproduced/metrics.json"
REPRODUCER=ROOT/"scripts/reproduce_pstart_v2_fixture_minutes.py"
OUTPUT=BASE/"v2_baseline_feature_matrix.csv.gz"


def exact_frozen_duration_constants():
    """Parse, don't re-tune or introduce substitute duration constants."""
    source=ast.parse(REPRODUCER.read_text(encoding="utf-8"))
    requested={"ROLE_H","DUR_H","LI","LS"}
    vals={}
    for node in source.body:
        if isinstance(node,ast.Assign):
            for index,field in enumerate(node.targets):
                if isinstance(field,ast.Tuple):
                    names=[x.id for x in field.elts if isinstance(x,ast.Name)]
                    if names==["ROLE_H","DUR_H","LI","LS"]:
                        numbers=ast.literal_eval(node.value)
                        vals=dict(zip(names,map(float,numbers)))
    if set(vals)!=requested:
        # Historical source uses a semicolon-delimited plain assignment, still AST.
        for node in source.body:
            if isinstance(node,ast.Assign):
                for var in node.targets:
                    if isinstance(var,ast.Name) and var.id in requested:
                        vals[var.id]=float(ast.literal_eval(node.value))
    if set(vals)!=requested:
        raise ValueError("Cannot recover original Phase 3A frozen minute constants")
    return vals


def build(target=None, past=None, persist=True):
    if target is None and (not INPUT.exists() or not HISTORY.exists()):
        raise FileNotFoundError("Build restored live sequence and performance first")
    target=pd.read_csv(INPUT,low_memory=False) if target is None else target.copy()
    past=pd.read_csv(HISTORY,low_memory=False) if past is None else past.copy()
    if target.empty or (persist and past.empty):
        raise ValueError("No live targets or historical observations")
    source=json.loads(COEFS.read_text())
    if source.get("train_seasons")!=["2023-24","2024-25"] or source.get("holdout")!="2025-26":
        raise ValueError("Frozen v2 coefficients are not from approved history")
    coef=source["coefficients"]
    required={"intercept","fast","slow","recent_mins","last_start","last_mins",
              "pos_DEF","pos_FWD","pos_GK","pos_GKP","pos_MID"}
    if set(coef)!=required:
        raise ValueError("Frozen v2 coefficient schema mismatch")
    if source["half_lives"]!={"fast":3.,"slow":10.,"minutes":3.}:
        raise ValueError("Frozen v2 baseline half lives modified")
    constants=exact_frozen_duration_constants()
    if not target.gw.nunique()==1:
        raise ValueError("Expected one as-of origin across GW6-11")
    origin=int(target.gw.iloc[0])
    origin_cut=pd.to_datetime(target.cutoff,utc=True,errors="raise")
    if origin_cut.isna().any():
        raise ValueError("Missing prediction cutoff")
    past["known_at"]=pd.to_datetime(past.available_at,utc=True,errors="raise")
    if past.gw.ge(origin).any():
        raise ValueError("Future gameweek results in baseline history")
    past=past[past.known_at<origin_cut.min()].copy()
    past["started"]=pd.to_numeric(past.started,errors="coerce")
    past["minutes"]=pd.to_numeric(past.minutes,errors="coerce")
    if past[["started","minutes"]].isna().any().any():
        raise ValueError("Historical starts/minutes incomplete")
    if not past.started.isin([0,1]).all() or (~past.minutes.between(0,90)).any():
        raise ValueError("Invalid observed starts or minutes")
    past=past.sort_values(["player_uuid","gw","known_at","fixture_uuid"])
    by_player=defaultdict(list)
    for r in past.itertuples(index=False):
        by_player[str(r.player_uuid)].append({
            "gw":int(r.gw),"started":int(r.started),"minutes":float(r.minutes)})
    features=[];durations=[]
    for r in target.itertuples(index=False):
        h=by_player.get(str(r.player_uuid),[])
        def wavg(field,half,default):
            vals=[];weights=[]
            for row in h:
                lag=max(1,int(origin-row["gw"]))
                w=2.0**(-lag/half)
                vals.append(row["started"] if field=="start" else row["minutes"]/90.)
                weights.append(w)
            return float(np.average(vals,weights=weights)) if weights else default
        fast=wavg("start",3.,.25)
        slow=wavg("start",10.,.25)
        minu=wavg("mins",3.,.25)
        previous=[z for z in h if z["gw"]==origin-1]
        last_start=float(np.mean([z["started"] for z in previous])) if previous else fast
        last_mins=float(np.mean([z["minutes"] for z in previous]))/90. if previous else minu
        pos=str(r.pos)
        # Preserve old FPL keeper code semantics. DO NOT map defenders to other positions.
        if pos not in ("GK","GKP","DEF","MID","FWD"):
            raise ValueError("Unsupported historical FPL position "+pos)
        x=dict(fast=fast,slow=slow,recent_mins=minu,last_start=last_start,
               last_mins=last_mins,
               **{"pos_"+k:float(pos==k) for k in ("DEF","FWD","GK","GKP","MID")})
        raw=float(coef["intercept"]+sum(float(coef[k])*x[k] for k in x))
        features.append(float(expit(raw)))
        p=project_minutes(
            h,role_half_life=constants["ROLE_H"],
            duration_half_life=constants["DUR_H"],
            start_logit_intercept=constants["LI"],
            start_logit_slope=constants["LS"],
            availability=1.)
        durations.append((float(p.expected_minutes_given_start),
                          float(p.expected_minutes_given_cameo),
                          float(p.p_cameo_given_bench)))
    pstart=normalize_eleven(target,np.asarray(features,dtype=float))
    if not np.isfinite(pstart).all() or not ((0<=pstart)&(pstart<=1)).all():
        raise ValueError("Invalid frozen P(start) baseline probabilities")
    exact=target[["fixture_uuid","team_id"]].copy()
    exact["p"]=pstart
    err=float((exact.groupby(["fixture_uuid","team_id"]).p.sum()-11).abs().max())
    if err>1e-6:raise ValueError("Original baseline exact XI constraint failed")
    result=target.copy()
    if any(x in result for x in ("base_logit","start_minutes_mean",
                                  "cameo_minutes_mean","p_cameo_given_bench")):
        raise ValueError("No overwrite of preexisting MM component priors")
    result["base_logit"]=logit(np.clip(pstart,1e-6,1-1e-6))
    for i,name in enumerate(("start_minutes_mean","cameo_minutes_mean",
                              "p_cameo_given_bench")):
        result[name]=[d[i] for d in durations]
    if not np.isfinite(result[["base_logit","start_minutes_mean",
        "cameo_minutes_mean","p_cameo_given_bench"]].to_numpy(float)).all():
        raise ValueError("Invalid minutes component")
    durations_range=(float(result.start_minutes_mean.min()),float(result.start_minutes_mean.max()),
                     float(result.cameo_minutes_mean.min()),float(result.cameo_minutes_mean.max()))
    if durations_range[0]<-1e-8 or durations_range[1]>90+1e-8 or durations_range[2]<-1e-8 or durations_range[3]>90+1e-8:
        raise ValueError(f"Duration out of range: {durations_range}")
    if not result.p_cameo_given_bench.between(0,1).all():
        raise ValueError("Cameo probability out of range")
    if len(result)!=len(target) or result.duplicated(["fixture_uuid","player_uuid"]).any():
        raise ValueError("Baseline broke fixture/player identity")
    if persist and any(x in result for x in ("y","outcome_known_at","minutes")):
        raise ValueError("Future target labels entered output")
    if persist: result.to_csv(OUTPUT,index=False,compression="gzip")
    report={
        "classification":"frozen_v2_MM_baseline_features_only_NOT_final_MM_or_PM",
        "origin_gw":origin,
        "targets":len(result),"historical_rows":len(past),
        "historical_training_coefficients":str(COEFS.relative_to(ROOT)),
        "baseline_exact11_max_error":err,
        "original_conditional_duration_constants":constants,
        "players_with_observed_history":sum(bool(by_player.get(str(x))) for x in target.player_uuid.unique()),
        "outcomes_from_target_used":0,
        "no_new_fit_or_parameters":True,
    }
    if persist: (ROOT/"work/live-final-model/live_baseline_provenance.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    print("FROZEN LIVE BASELINE/CONDITIONAL MINUTES",json.dumps(report),flush=True)
    return result


if __name__=="__main__":
    build()

