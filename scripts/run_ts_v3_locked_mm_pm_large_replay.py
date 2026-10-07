#!/usr/bin/env python3
"""Large TS v3 replay with locked Team News MM + frozen vFinal PM.

GW1-21 state is reconstructed from the accounting-valid robust TS v3 proxy:
rho=.60 weights, hit buffer 1.0. From GW22 onward, locked MM+PM is rebuilt
walk-forward, converted to a current-deadline correction versus Phase5Q, and
that correction is frozen across the visible 6GW horizon (no future leakage).

TS v3 mechanics remain frozen: receding 6GW, state=squad+bank+FT+purchase
prices, 0-5 transfers, official 4pt hits, uncertainty buffer only on paid
transfers, execute first action only, XI/captain optimized per GW, chips OFF.
"""
from __future__ import annotations
import json,sys,time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit,logit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"scripts"))

import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as base
from fpl_xpts.identity import resolve_uuid_to_fpl_ids
from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import OwnedPlayer,ReplayState,actual_team_points,legalize_team_limit,valid_squad
from fpl_xpts.transfer_planner import PlannerConfig,execute_first_action,plan_transfer_path
from run_pm_locked_mm_ab import build_locked_mm_predictions
from run_vfinal_integrated import build_final_frame,make_vfinal_input
from fpl_v1_1_model.paired_joint import run_pair

ROBUST=ROOT/"analysis/results/ts-v3-weight-buffer-grid-20261005-v1/exp_0.60_buffer_1.0"
OUT=ROOT/"analysis/results/ts-v3-locked-mm-pm-large-replay-20261007-v1"
WEIGHTS=(1.0,.60,.36,.216,.1296,.07776)
BUFFER=1.0
EARLY_POINTS=1046

def ints(cell):
    if pd.isna(cell) or str(cell).strip()=="":
        return []
    return [int(float(x)) for x in str(cell).split(";") if str(x).strip() and str(x)!="nan"]

def mapping_uuid_to_id():
    feat=pd.read_csv(ROOT/"analysis/results/workload-recovered-v4/all_features.csv.gz",
                     usecols=["player_uuid","player"]).drop_duplicates()
    raw=hp.unpack_runtime("players_raw.csv").drop_duplicates("id").copy()
    mp,matches=resolve_uuid_to_fpl_ids(feat,raw)
    return mp,pd.DataFrame([m.__dict__ for m in matches])

def build_current_locked_pm():
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
        oi,_=make_vfinal_input(old[old.fixture_uuid==fx])
        ni,_=make_vfinal_input(ng)
        _,rn=run_pair(oi,ni,n=400,seed=73192001+i)
        for r in ng.itertuples(index=False):
            pid=str(r.player_uuid)
            pplay=float(r.new_p_start+(1-r.new_p_start)*r.new_q_sub)
            rows.append(dict(gw=int(r.gw),fixture_uuid=fx,player_uuid=pid,
                             new_xpts=float(rn[pid]["xPts"]),p_play_fixture=pplay))
        if (i+1)%20==0:
            print("PM fixtures",i+1,"/",new.fixture_uuid.nunique(),flush=True)
    p=pd.DataFrame(rows)
    mp,detail=mapping_uuid_to_id()
    p["id"]=p.player_uuid.astype(str).map(mp)
    total_uuid=int(p.player_uuid.nunique())
    mapped_uuid=int(p.loc[p.id.notna(),"player_uuid"].nunique())
    p=p[p.id.notna()].copy();p.id=p.id.astype(int)
    xp=p.groupby(["gw","id"],as_index=False).agg(vfinal_xp=("new_xpts","sum"))
    play=p.groupby(["gw","id"],as_index=False).agg(
        p_no_play=("p_play_fixture",lambda s:float(np.prod(1-np.clip(s,0,1)))))
    play["vfinal_p_play"]=1-play.p_no_play
    return xp.merge(play[["gw","id","vfinal_p_play"]],on=["gw","id"],how="left"),mapped_uuid,total_uuid,detail

def reconstruct_gw22_state(gws,names,forecast):
    plans=pd.read_csv(ROBUST/"tsv3_plans.csv")
    meta1=hp.gw_meta(gws,names,1)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    from fpl_xpts.season_replay import initial_squad
    state=initial_squad(origin1,meta1,[1])
    for gw in range(1,22):
        q=plans[(plans.origin_gw==gw)&
                (plans.is_executed.astype(str).str.lower().isin(["true","1"]))]
        if q.empty: continue
        r=q.iloc[0]
        meta=hp.gw_meta(gws,names,gw).drop_duplicates("id").set_index("id")
        for pid in ints(r.outgoing): state.squad.pop(pid)
        for pid in ints(r.incoming):
            state.squad[pid]=OwnedPlayer(pid,int(meta.loc[pid,"price_tenths"]))
        state.bank=int(round(float(r.bank_after)*10))
        state.free_transfers=int(r.free_transfers_after)
    return state

def apply_full_horizon_correction(origin,gw,vf):
    out=origin.copy()
    cur_base=(out[out.gw==gw][["id","xpts_mean","p_play"]]
              .groupby("id",as_index=False)
              .agg(base_xp=("xpts_mean","sum"),base_p_play=("p_play","max")))
    cur=vf[vf.gw==gw][["id","vfinal_xp","vfinal_p_play"]]
    z=cur_base.merge(cur,on="id",how="inner")
    if z.empty:return out,0,len(cur_base)
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
    exact=dict(zip(z.id.astype(int),z.vfinal_xp.astype(float)))
    pexact=dict(zip(z.id.astype(int),z.vfinal_p_play.astype(float)))
    cm=out.gw.eq(gw)&out.id.astype(int).isin(exact)
    out.loc[cm,"xpts_mean"]=out.loc[cm].id.astype(int).map(exact)
    out.loc[cm,"p_play"]=out.loc[cm].id.astype(int).map(pexact)
    return out,len(z),len(cur_base)

def current_projection(origin,meta,gw):
    stripped=origin.drop(columns=[c for c in
        ["meta_team","meta_price_tenths","meta_web_name","meta_position"] if c in origin.columns])
    return hp.complete_current_projection(stripped,meta,gw)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    vf,mapped,total_uuid,identity=build_current_locked_pm()
    identity.to_csv(OUT/"identity_resolution.csv",index=False)
    gws,names,forecast=base.prepare()
    state=reconstruct_gw22_state(gws,names,forecast)

    known=hp.gw_meta(gws,names,1)
    for seen in range(2,22):
        obs=hp.gw_meta(gws,names,seen)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates("id",keep="last")

    config=PlannerConfig(weights=WEIGHTS,hit_uncertainty_buffer=BUFFER,beam_width=20,
                         candidates_per_transfer_count=1,candidate_limit_per_position=18,
                         top_targets_per_position=18,local_bundle_beam=60,candidate_return_per_depth=12,
                         max_transfers_per_week=5,candidate_backend="fast_local",milp_time_limit=2.0)
    total=0;logs=[];plans=[]
    for gw in range(22,39):
        t0=time.perf_counter()
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates("id",keep="last")
        meta=known.copy()
        origin=base.origin_with_meta(forecast,meta,gw)
        origin,ncorr,ncur=apply_full_horizon_correction(origin,gw,vf)

        ft_before=int(state.free_transfers)
        forced=legalize_team_limit(state,meta,origin,gw)
        forced_n=len(forced)
        if forced_n:
            # Mandatory real-life club-limit repairs consume FT before optional moves.
            state.free_transfers=max(0,ft_before-forced_n)

        result=plan_transfer_path(state,meta,origin,gw,config)
        optional=execute_first_action(state,result,meta)
        total_tx=forced_n+len(optional)
        if total_tx>5:
            raise RuntimeError(f"GW{gw}: >5 total transfers ({total_tx})")
        hit=sum(int(x.get("hit",0)) for x in forced)+sum(int(x.get("hit",0)) for x in optional)
        expected_hit=4*max(0,total_tx-ft_before)
        if hit!=expected_hit:
            raise RuntimeError(f"GW{gw}: hit mismatch {hit} vs {expected_hit}; FT={ft_before}, tx={total_tx}")
        if not valid_squad(meta,state.squad):
            raise RuntimeError(f"GW{gw}: invalid squad")
        if state.bank<0: raise RuntimeError(f"GW{gw}: negative bank")

        current=current_projection(origin,meta,gw)
        plan=plan_squad(current,list(state.squad),gw)
        score,_=actual_team_points(plan.rows,hp.actual_gw(gws,gw),None,hit)
        total+=score
        logs.append(dict(gw=gw,score=int(score),cumulative=int(total),
                         transfers=int(total_tx),forced_transfers=int(forced_n),
                         hit_points=int(hit),free_transfers_before=ft_before,
                         free_transfers_after=int(state.free_transfers),bank=state.bank/10,
                         corrected_players=int(ncorr),current_players=int(ncur),
                         correction_share=float(ncorr/ncur) if ncur else 0.,
                         runtime_seconds=float(time.perf_counter()-t0)))
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
        pd.DataFrame(logs).to_csv(OUT/"gameweek_log.csv",index=False)
        pd.DataFrame(plans).to_csv(OUT/"plans.csv",index=False)
        print(f"GW{gw}: score={score} cum={total} tx={total_tx} hit={hit} FT={state.free_transfers}",flush=True)

    late_reference=984
    full_total=EARLY_POINTS+total
    summary={
      "classification":"large TS v3 replay with locked MM+PM; GW22-38 continuation from robust GW1-21 state",
      "weights":list(WEIGHTS),"hit_uncertainty_buffer":BUFFER,
      "ts_mechanics":"locked v3 fast_local rolling/receding 6GW; execute first action only; chips OFF",
      "points_gw1_21_carried":EARLY_POINTS,
      "points_gw22_38_new_mm_pm":int(total),
      "full_season_combined":int(full_total),
      "old_same_state_gw22_38_reference":late_reference,
      "delta_gw22_38_vs_old_pm":int(total-late_reference),
      "old_robust_fullseason_reference":2030,
      "delta_fullseason_vs_old_pm":int(full_total-2030),
      "transfers_gw22_38":int(sum(x["transfers"] for x in logs)),
      "hits_gw22_38":int(sum(x["hit_points"] for x in logs)),
      "identity_coverage":{"mapped_uuid":mapped,"total_uuid":total_uuid,
                           "share":float(mapped/total_uuid)},
      "future_horizon_method":"current-deadline locked-MM+PM vs Phase5Q correction frozen across d..d+5",
      "future_information_leakage":False,
      "warning":"GW1-21 remains the prior cutoff-safe Phase5Q-based robust TS state; future GW+1..+5 PM is a deadline-frozen correction proxy rather than component-by-component regenerated final PM."
    }
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":main()
