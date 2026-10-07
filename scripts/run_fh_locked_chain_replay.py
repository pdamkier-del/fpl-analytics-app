#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_transfer_strategy_v3_replay as ts
import run_horizon_policy_comparison as hp
from fpl_xpts.chip_planner import optimize_free_hit_squad,decide_fh_from_samples,ChipPlannerConfig
from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import actual_team_points,initial_squad,legalize_team_limit,valid_squad,ReplayState,OwnedPlayer
from fpl_xpts.transfer_planner import PlannerConfig,plan_transfer_path,execute_first_action,clone_state

WEIGHTS=(1.0,.60,.36,.216,.1296,.07776)
BUFFER=1.0

def apply_hypothetical(state,action,meta):
    prices=meta.drop_duplicates('id').set_index('id').price_tenths.astype(int).to_dict()
    for pid in action.outgoing:
        state.squad.pop(int(pid),None)
    for pid in action.incoming:
        state.squad[int(pid)]=OwnedPlayer(int(pid),int(prices[int(pid)]))
    state.bank=int(action.bank_after)
    state.free_transfers=int(action.free_transfers_after)

def future_fh_values(state,meta,origin,result,current_gw,period_end):
    rows=[]
    hstate=clone_state(state)
    for a in result.path:
        gw=int(a.gw)
        if gw>period_end: break
        normal_net=float(a.projected_manager_score)-float(a.official_hit_points)
        fh=optimize_free_hit_squad(state=hstate,meta=meta,forecast=origin,gw=gw,normal_score=normal_net)
        rows.append(dict(simulation=0,gw=gw,points=float(fh['fh_gain'])))
        apply_hypothetical(hstate,a,meta)
    return pd.DataFrame(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--vfinal',required=True)
    ap.add_argument('--out',required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)

    gws,names,cold=ts.prepare()
    cold=cold[cold.origin_gw<=4].copy()
    vf=pd.read_csv(a.vfinal)
    vf['web_name']=vf.id.astype(int).map(names).fillna(vf.id.astype(str))
    keep=['id','web_name','position','gw','origin_gw','xpts_mean','p_play','fixtures']
    vf=vf[keep].copy();vf.id=vf.id.astype(int)
    forecast=pd.concat([cold[keep],vf],ignore_index=True)

    meta1=hp.gw_meta(gws,names,1)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    state=initial_squad(origin1,meta1,[1])
    known=meta1.copy();logs=[];fh_used=[];normal_total=0;fh_total=0
    config=PlannerConfig(weights=WEIGHTS,hit_uncertainty_buffer=BUFFER,beam_width=20,
        candidates_per_transfer_count=1,candidate_limit_per_position=18,top_targets_per_position=18,
        local_bundle_beam=60,candidate_return_per_depth=12,max_transfers_per_week=5,
        candidate_backend='fast_local',milp_time_limit=2.0)
    chip_cfg=ChipPlannerConfig(future_discount=.97,min_use_edge=0.0)

    for gw in range(1,39):
        t0=time.perf_counter()
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin_raw=forecast[forecast.origin_gw==gw-1].copy()
        current=hp.complete_current_projection(origin_raw,meta,gw)
        origin=ts.origin_with_meta(forecast,meta,gw)

        forced=[]
        if gw>1: forced=legalize_team_limit(state,meta,origin,gw)
        pre_ts=clone_state(state)
        result=plan_transfer_path(state,meta,origin,gw,config)

        half=1 if gw<=19 else 2
        period_end=19 if half==1 else 38
        can_fh=half not in fh_used
        values=future_fh_values(pre_ts,meta,origin,result,gw,period_end) if can_fh else pd.DataFrame()
        if can_fh and not values.empty:
            decision=decide_fh_from_samples(values,current_gw=gw,period_end_gw=period_end,config=chip_cfg)
        else:
            decision={'action':'SAVE_FH','use_now_value':None,'save_option_value':None,'use_edge':None,'forced_by_expiry':False}

        normal_state=clone_state(state)
        transfers=execute_first_action(normal_state,result,meta)
        hit_cost=sum(int(x.get('hit',0)) for x in transfers)+sum(int(x.get('hit',0)) for x in forced)
        if not valid_squad(meta,normal_state.squad): raise RuntimeError(f'GW{gw}: invalid normal squad')
        normal_plan=plan_squad(current,list(normal_state.squad),gw)
        normal_score,_=actual_team_points(normal_plan.rows,hp.actual_gw(gws,gw),None,hit_cost)
        normal_total+=normal_score

        use_fh=can_fh and decision['action']=='USE_FH'
        if use_fh:
            normal_net_xp=float(result.first_action.projected_manager_score)-float(result.first_action.official_hit_points) if result.first_action else float(normal_plan.expected_score)
            fh=optimize_free_hit_squad(state=pre_ts,meta=meta,forecast=origin,gw=gw,normal_score=normal_net_xp)
            fh_plan=fh['plan_rows']
            score,_=actual_team_points(fh_plan,hp.actual_gw(gws,gw),'free_hit',0)
            fh_used.append(half)
            # Free Hit does not execute TS transfers or mutate persistent squad.
            # Forced legalisation happened before the chip decision and remains persistent.
            state=pre_ts
            state.free_transfers=min(5,int(state.free_transfers)+1)
            selected=';'.join(map(str,fh['fh_squad_ids']))
            cap=int(fh['fh_captain_id'])
        else:
            score=normal_score
            state=normal_state
            selected='';cap=None
        fh_total+=score

        logs.append(dict(gw=gw,half=half,fh_action=decision['action'],fh_used=use_fh,
            fh_expected_gain=decision.get('use_now_value'),fh_save_option=decision.get('save_option_value'),
            fh_use_edge=decision.get('use_edge'),fh_forced=decision.get('forced_by_expiry',False),
            normal_actual_points=normal_score,actual_points_with_fh=score,actual_fh_gain=score-normal_score,
            fh_squad_ids=selected,fh_captain_id=cap,normal_hit_cost=hit_cost,
            bank=state.bank/10,free_transfers_after=state.free_transfers,runtime_seconds=time.perf_counter()-t0))
        print(f'GW{gw}: FH {decision["action"]} used={use_fh} normal={normal_score} withFH={score}',flush=True)

    log=pd.DataFrame(logs);log.to_csv(out/'fh_gameweek_log.csv',index=False)
    used=log[log.fh_used].copy();used.to_csv(out/'fh_decisions.csv',index=False)
    summary=dict(classification='2025/26 full-season Free Hit replay on locked chain',
        weights=list(WEIGHTS),hit_uncertainty_buffer=BUFFER,future_discount=.97,
        periods={'first':[1,19],'second':[20,38]},
        fh_decisions=used[['gw','half','fh_expected_gain','fh_save_option','fh_use_edge','fh_forced','normal_actual_points','actual_points_with_fh','actual_fh_gain']].to_dict('records'),
        normal_total_points=int(normal_total),total_points_with_fh=int(fh_total),
        realized_fh_gain=int(fh_total-normal_total),fh_chips_used=int(len(used)))
    (out/'summary.json').write_text(json.dumps(summary,indent=2,default=str)+'\n')
    print(json.dumps(summary,indent=2,default=str))

if __name__=='__main__': main()
