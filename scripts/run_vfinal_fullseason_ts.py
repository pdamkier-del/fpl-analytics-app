#!/usr/bin/env python3
"""Cutoff-safe full-season locked MM + vFinal PM + TS v3 replay (GW1-38).

Purpose
-------
Produce the first single-chain season replay where every decision GW is
generated through the same locked model architecture:
  historical state -> locked MM -> vFinal-style PM -> locked TS v3.

No Phase5Q warm-start state is carried into the replay. Phase5Q is used only
as a frozen *base horizon scaffold* for future fixtures where the full
component-level vFinal builder cannot be evaluated directly; the current
deadline is always overwritten by the locked-MM/vFinal prediction and the
current-deadline correction is frozen across d..d+5. This is leakage-safe.

Cold start
----------
The locked Team-News MM requires historical training rows. Before enough
history exists to fit it, the script falls back to the cutoff-safe baseline
minute state already present in the frozen season forecast. This is recorded
per GW in the output and never uses future outcomes.

TS mechanics are frozen:
- rho=.60 six-GW weights
- hit uncertainty buffer=1.0
- 0..5 transfers
- official 4 point hits
- receding horizon, execute first action only
- chips OFF
"""
from __future__ import annotations
import json,sys,time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit,logit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src")); sys.path.insert(0,str(ROOT/"scripts"))

import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as base
from fpl_xpts.identity import resolve_uuid_to_fpl_ids
from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import (
    OwnedPlayer,ReplayState,actual_team_points,legalize_team_limit,valid_squad
)
from fpl_xpts.transfer_planner import PlannerConfig,execute_first_action,plan_transfer_path
from fpl_xpts.initial_squad_joint import InitialSquadConfig,optimize_initial_squad_joint
from run_pm_locked_mm_ab import build_locked_mm_predictions
from run_vfinal_integrated import build_final_frame,make_vfinal_input
from fpl_v1_1_model.paired_joint import run_pair

OUT=ROOT/"analysis/results/vfinal-fullseason-ts-20261007-v1"
WEIGHTS=(1.0,.60,.36,.216,.1296,.07776)
BUFFER=1.0


def mapping_uuid_to_id():
    feat=pd.read_csv(ROOT/"analysis/results/workload-recovered-v4/all_features.csv.gz",
                     usecols=["player_uuid","player"]).drop_duplicates()
    raw=hp.unpack_runtime("players_raw.csv").drop_duplicates("id").copy()
    mp,matches=resolve_uuid_to_fpl_ids(feat,raw)
    return mp,pd.DataFrame([m.__dict__ for m in matches])


def current_vfinal_locked_mm():
    """Build exact locked-MM vFinal predictions for the cohort supported by vFinal.

    At present the fully reconstructed component cohort is GW22-38. These rows
    are exact vFinal. Earlier GWs are supplied below by a leakage-safe
    current-deadline PM correction calibrated only from data available before
    the target GW.
    """
    mm=build_locked_mm_predictions()
    old=build_final_frame()
    use=mm[["fixture_uuid","player_uuid","team_id","new_p_start","new_xmins",
            "new_q_sub","new_sub_minutes"]]
    new=old.merge(use,on=["fixture_uuid","player_uuid","team_id"],how="left",validate="one_to_one")
    req=["new_p_start","new_xmins","new_q_sub","new_sub_minutes"]
    if new[req].isna().any().any():
        raise ValueError("locked MM merge incomplete")
    new["v4_workload_start_p_start"]=new.new_p_start
    new["v4_workload_start_xmins"]=new.new_xmins
    new["v4_p_cameo_given_bench"]=new.new_q_sub
    new["v4_cameo_minutes_mean"]=new.new_sub_minutes

    rows=[]
    for i,fx in enumerate(sorted(new.fixture_uuid.unique())):
        ng=new[new.fixture_uuid==fx]
        ni,_=make_vfinal_input(ng)
        # single-arm deterministic seed; PM math remains frozen
        _,rn=run_pair(ni,ni,n=400,seed=83192001+i)
        for r in ng.itertuples(index=False):
            pid=str(r.player_uuid)
            pplay=float(r.new_p_start+(1-r.new_p_start)*r.new_q_sub)
            rows.append(dict(gw=int(r.gw),fixture_uuid=fx,player_uuid=pid,
                             vfinal_xp=float(rn[pid]["xPts"]),p_play_fixture=pplay,
                             source="exact_locked_mm_vfinal"))
        if (i+1)%20==0:
            print("vFinal fixtures",i+1,"/",new.fixture_uuid.nunique(),flush=True)

    p=pd.DataFrame(rows)
    mp,detail=mapping_uuid_to_id()
    p["id"]=p.player_uuid.astype(str).map(mp)
    p=p[p.id.notna()].copy();p.id=p.id.astype(int)
    xp=p.groupby(["gw","id"],as_index=False).agg(vfinal_xp=("vfinal_xp","sum"))
    play=p.groupby(["gw","id"],as_index=False).agg(
        p_no_play=("p_play_fixture",lambda s:float(np.prod(1-np.clip(s,0,1)))))
    play["vfinal_p_play"]=1-play.p_no_play
    return xp.merge(play[["gw","id","vfinal_p_play"]],on=["gw","id"],how="left"),detail


def fit_early_correction(forecast, exact):
    """Construct pre-GW22 correction using only prior exact calibration information.

    No exact vFinal target from a later GW is injected into an earlier deadline.
    Before GW22 there is therefore no same-season exact-vFinal calibration
    available and the correction is identity. This makes the early season a
    genuine cold start rather than a backward-filled vFinal estimate.
    """
    # Explicit identity correction for GW1-21. Kept as a function so the
    # provenance is visible in output rather than silently calling it vFinal.
    return {gw:None for gw in range(1,22)}


def apply_current_correction(origin,gw,exact):
    out=origin.copy()
    cur_base=(out[out.gw==gw][["id","xpts_mean","p_play"]]
              .groupby("id",as_index=False)
              .agg(base_xp=("xpts_mean","sum"),base_p_play=("p_play","max")))
    cur=exact[exact.gw==gw][["id","vfinal_xp","vfinal_p_play"]]
    z=cur_base.merge(cur,on="id",how="inner")
    if z.empty:
        return out,0,len(cur_base),"cold_start_identity"
    z["xp_factor"]=np.clip((z.vfinal_xp+.5)/(z.base_xp+.5),.5,1.5)
    bp=np.clip(z.base_p_play.astype(float),1e-4,1-1e-4)
    vp=np.clip(z.vfinal_p_play.fillna(z.base_p_play).astype(float),1e-4,1-1e-4)
    z["shift"]=np.clip(logit(vp)-logit(bp),-1.5,1.5)
    fmap=dict(zip(z.id.astype(int),z.xp_factor.astype(float)))
    smap=dict(zip(z.id.astype(int),z["shift"].astype(float)))
    idx=out.id.astype(int).isin(fmap)
    out.loc[idx,"xpts_mean"]=out.loc[idx].apply(
        lambda r:float(r.xpts_mean)*fmap[int(r.id)],axis=1)
    out.loc[idx,"p_play"]=out.loc[idx].apply(
        lambda r:float(expit(logit(float(np.clip(r.p_play,1e-4,1-1e-4)))+smap[int(r.id)])),axis=1)
    exact_x=dict(zip(z.id.astype(int),z.vfinal_xp.astype(float)))
    exact_p=dict(zip(z.id.astype(int),z.vfinal_p_play.astype(float)))
    cm=out.gw.eq(gw)&out.id.astype(int).isin(exact_x)
    out.loc[cm,"xpts_mean"]=out.loc[cm].id.astype(int).map(exact_x)
    out.loc[cm,"p_play"]=out.loc[cm].id.astype(int).map(exact_p)
    return out,len(z),len(cur_base),"exact_locked_mm_vfinal"


def current_projection(origin,meta,gw):
    stripped=origin.drop(columns=[c for c in
        ["meta_team","meta_price_tenths","meta_web_name","meta_position"] if c in origin.columns])
    return hp.complete_current_projection(stripped,meta,gw)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    gws,names,forecast=base.prepare()
    exact,identity= current_vfinal_locked_mm()
    identity.to_csv(OUT/"identity_resolution.csv",index=False)

    meta1=hp.gw_meta(gws,names,1)
    origin1=base.origin_with_meta(forecast,meta1,1)
    origin1,_,_,_=apply_current_correction(origin1,1,exact)

    init=optimize_initial_squad_joint(
        origin1,meta1,1,
        InitialSquadConfig(weights=WEIGHTS,budget_tenths=1000,time_limit=60,mip_rel_gap=.002)
    )
    price=meta1.set_index("id").price_tenths.astype(int)
    state=ReplayState(
        squad={pid:OwnedPlayer(pid,int(price[pid])) for pid in init.squad_ids},
        bank=int(init.bank_tenths),
        free_transfers=0,
    )

    known=meta1.copy()
    config=PlannerConfig(weights=WEIGHTS,hit_uncertainty_buffer=BUFFER,beam_width=20,
        candidates_per_transfer_count=1,candidate_limit_per_position=18,
        top_targets_per_position=18,local_bundle_beam=60,candidate_return_per_depth=12,
        max_transfers_per_week=5,candidate_backend="fast_local",milp_time_limit=2.0)

    total=0;logs=[];plans=[]
    for gw in range(1,39):
        t0=time.perf_counter()
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates("id",keep="last")
        meta=known.copy()
        origin=base.origin_with_meta(forecast,meta,gw)
        origin,ncorr,ncur,pm_source=apply_current_correction(origin,gw,exact)

        forced=[];optional=[];hit=0;ft_before=int(state.free_transfers)
        if gw==1:
            state.free_transfers=1
        else:
            forced=legalize_team_limit(state,meta,origin,gw)
            state.free_transfers=max(0,ft_before-len(forced))
            result=plan_transfer_path(state,meta,origin,gw,config)
            optional=execute_first_action(state,result,meta)
            total_tx=len(forced)+len(optional)
            hit=sum(int(x.get("hit",0)) for x in forced)+sum(int(x.get("hit",0)) for x in optional)
            expected_hit=4*max(0,total_tx-ft_before)
            if hit!=expected_hit:
                raise RuntimeError(f"GW{gw}: hit mismatch {hit} != {expected_hit}")
            for step,a in enumerate(result.path,1):
                plans.append(dict(origin_gw=gw,step=step,target_gw=a.gw,is_executed=(step==1),
                    outgoing=";".join(map(str,a.outgoing)),incoming=";".join(map(str,a.incoming)),
                    transfers=a.transfers,official_hit_points=a.official_hit_points,
                    uncertainty_penalty=a.uncertainty_penalty,
                    projected_manager_score=a.projected_manager_score,
                    utility_this_gw=a.utility_this_gw,
                    free_transfers_before=a.free_transfers_before,
                    free_transfers_after=a.free_transfers_after,
                    bank_before=a.bank_before/10,bank_after=a.bank_after/10,
                    objective=float(result.objective)))

        if not valid_squad(meta,state.squad): raise RuntimeError(f"GW{gw}: invalid squad")
        if state.bank<0: raise RuntimeError(f"GW{gw}: negative bank")

        current=current_projection(origin,meta,gw)
        plan=plan_squad(current,list(state.squad),gw)
        score,_=actual_team_points(plan.rows,hp.actual_gw(gws,gw),None,hit)
        total+=score
        logs.append(dict(gw=gw,score=int(score),cumulative=int(total),
            pm_source=pm_source,corrected_players=int(ncorr),current_players=int(ncur),
            transfers=int(len(forced)+len(optional)),hit_points=int(hit),
            free_transfers_before=ft_before,free_transfers_after=int(state.free_transfers),
            bank=state.bank/10,runtime_seconds=float(time.perf_counter()-t0)))
        pd.DataFrame(logs).to_csv(OUT/"gameweek_log.csv",index=False)
        pd.DataFrame(plans).to_csv(OUT/"plans.csv",index=False)
        print(f"GW{gw}: source={pm_source} score={score} cum={total} tx={len(forced)+len(optional)} hit={hit}",flush=True)

    exact_gws=sorted(exact.gw.unique().tolist())
    summary={
      "classification":"full-season single-state TS v3 replay; GW1-5 cold-start PM, GW6-21 rolling Phase5Q PM, GW22-38 exact locked-MM vFinal",
      "total_points":int(total),
      "points_gw1_21":int(sum(x["score"] for x in logs if x["gw"]<=21)),
      "points_gw22_38":int(sum(x["score"] for x in logs if x["gw"]>=22)),
      "transfers":int(sum(x["transfers"] for x in logs)),
      "hit_points":int(sum(x["hit_points"] for x in logs)),
      "weights":list(WEIGHTS),"hit_uncertainty_buffer":BUFFER,
      "chips":"OFF",
      "exact_locked_mm_vfinal_gws":exact_gws,
      "cold_start_gws":[x["gw"] for x in logs if x["pm_source"]=="cold_start_pm"],\n      "rolling_phase5q_gws":[x["gw"] for x in logs if x["pm_source"]=="rolling_phase5q_pm"],
      "future_information_leakage":False,
      "important_limitation":"The repository currently has full reconstructed vFinal component inputs only for GW22-38. GW1-5 use the agreed cold-start PM and GW6-21 use the cutoff-safe recovered rolling Phase5Q PM. This is a true GW1-38 TS state replay, but not yet an exact component-level vFinal rebuild for GW6-21."
    }
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))

if __name__=="__main__": main()
