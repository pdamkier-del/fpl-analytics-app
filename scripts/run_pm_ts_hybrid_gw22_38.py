#!/usr/bin/env python3
"""GW22-38 PM+TS integration diagnostic.

This is the first direct interaction test between:
- PM: integrated vFinal current-GW xPts/minutes (cutoff-safe at that GW)
- TS: TS v4 joint rolling MILP

Important boundary:
vFinal has not yet been regenerated for all earlier origin->future target cells.
Therefore the current decision GW uses vFinal, while GW+1..GW+5 retain the
already recovered cutoff-frozen Phase5Q horizon. This is a HYBRID integration
diagnostic, not the final all-vFinal rolling season replay.

The purpose is to test whether the new PM changes the actual TS decisions and
GW22-38 realized score without leaking target-deadline vFinal into future GWs.
"""
from __future__ import annotations
import json,sqlite3,sys,time
from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as base
from run_v4_performance_rating_experiment import player_id_map
from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import OwnedPlayer,ReplayState,actual_team_points,initial_squad,valid_squad
from fpl_xpts.transfer_planner import execute_first_action
from fpl_xpts.transfer_planner_joint import JointPlannerConfig,plan_transfer_path_joint

ART=ROOT/'analysis/results/transfer-strategy-v4-joint-replay-20261006-v1'
VFINAL=ROOT/'analysis/results/vfinal-integrated-20261005-v1'
MINS=ROOT/'analysis/results/v4-combined-minutes-20261005-v1/reused_diagnostic_predictions.csv.gz'
OUT=ROOT/'analysis/results/pm-ts-hybrid-gw22-38-20261006-v1'
WEIGHTS=(1.00,.85,.70,.55,.40,.25)
BUFFER=1.5


def ints(cell):
    if pd.isna(cell) or str(cell).strip()=='':
        return []
    return [int(float(x)) for x in str(cell).split(';') if x and x!='nan']


def mapping_uuid_to_id(gws,names):
    direct=player_id_map()
    out={str(uuid):int(pid) for pid,uuid in direct.items()}
    need=set(pd.read_csv(VFINAL/'predictions.csv.gz',usecols=['player_uuid']).player_uuid.astype(str))
    missing=sorted(need-set(out))
    if missing:
        raise RuntimeError(f'unresolved vFinal UUID->FPL ids: {len(missing)} first={missing[:10]}')
    return out


def reconstruct_state_at_gw22(gws,names,forecast):
    plans=pd.read_csv(ART/'plans.csv')
    meta1=hp.gw_meta(gws,names,1)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    state=initial_squad(origin1,meta1,[1])
    for gw in range(1,22):
        q=plans[(plans.origin_gw==gw)&(plans.is_executed==True)]
        if q.empty:
            continue
        r=q.iloc[0]
        meta=hp.gw_meta(gws,names,gw).drop_duplicates('id').set_index('id')
        outs=ints(r.outgoing);ins=ints(r.incoming)
        for pid in outs:
            state.squad.pop(pid)
        for pid in ins:
            state.squad[pid]=OwnedPlayer(pid,int(meta.loc[pid,'price_tenths']))
        state.bank=int(round(float(r.bank_after)*10))
        state.free_transfers=int(r.free_transfers_after)
    return state


def vfinal_current_table(uuid_to_id):
    p=pd.read_csv(VFINAL/'predictions.csv.gz')
    p['id']=p.player_uuid.astype(str).map(uuid_to_id)
    p=p[p.id.notna()].copy();p.id=p.id.astype(int)
    x=p.groupby(['gw','id'],as_index=False).agg(xpts_mean=('vfinal_xpts','sum'))

    m=pd.read_csv(MINS)
    m['id']=m.player_uuid.astype(str).map(uuid_to_id)
    m=m[m.id.notna()].copy();m.id=m.id.astype(int)
    m['p_play_fixture']=m.combined_p_start+(1-m.combined_p_start)*m.combined_q_sub
    play=m.groupby(['gw','id'],as_index=False).agg(
        p_no_play=('p_play_fixture',lambda s:float(np.prod(1-np.clip(s,0,1)))))
    play['p_play']=1-play.p_no_play
    return x.merge(play[['gw','id','p_play']],on=['gw','id'],how='left')


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    gws,names,forecast=base.prepare()
    uuid_to_id=mapping_uuid_to_id(gws,names)
    vf=vfinal_current_table(uuid_to_id)
    state=reconstruct_state_at_gw22(gws,names,forecast)
    start_ids=sorted(state.squad)
    logs=[];plans=[];total=0

    for gw in range(22,39):
        meta=hp.gw_meta(gws,names,gw)
        origin=base.origin_with_meta(forecast,meta,gw)

        # Replace ONLY current-GW forecast with vFinal. Future horizon remains
        # cutoff-frozen Phase5Q; never inject later target-deadline vFinal.
        cur=vf[vf.gw==gw][['id','xpts_mean','p_play']].copy()
        if cur.empty:
            raise RuntimeError(f'GW{gw}: missing vFinal current-GW table')
        om=origin.gw.eq(gw)
        origin=origin.merge(cur,on='id',how='left',suffixes=('','_vf'))
        origin.loc[om & origin.xpts_mean_vf.notna(),'xpts_mean']=origin.loc[om & origin.xpts_mean_vf.notna(),'xpts_mean_vf']
        origin.loc[om & origin.p_play_vf.notna(),'p_play']=origin.loc[om & origin.p_play_vf.notna(),'p_play_vf']
        origin=origin.drop(columns=['xpts_mean_vf','p_play_vf'])

        cfg=JointPlannerConfig(
            weights=WEIGHTS,hit_uncertainty_buffer=BUFFER,max_transfers_per_week=5,
            time_limit=60.0,mip_rel_gap=.002,retry_time_limit=180.0,retry_mip_rel_gap=.01)
        t0=time.perf_counter()
        result=plan_transfer_path_joint(state,meta,origin,gw,cfg)
        rows=execute_first_action(state,result,meta)
        hit=sum(int(x.get('hit',0)) for x in rows)
        if not valid_squad(meta,state.squad): raise RuntimeError(f'GW{gw}: invalid squad')

        current=hp.complete_current_projection(origin,meta,gw)
        plan=plan_squad(current,list(state.squad),gw)
        score,_=actual_team_points(plan.rows,hp.actual_gw(gws,gw),None,hit)
        total+=score
        a=result.first_action
        logs.append(dict(gw=gw,score=int(score),cumulative=int(total),transfers=len(rows),
                         hit_cost=int(hit),bank=state.bank/10,free_transfers=state.free_transfers,
                         objective=float(result.objective),runtime_seconds=time.perf_counter()-t0))
        plans.append(dict(gw=gw,outgoing=';'.join(map(str,a.outgoing)),incoming=';'.join(map(str,a.incoming)),
                          transfers=a.transfers,hit=a.official_hit_points,
                          projected_manager_score=a.projected_manager_score))
        pd.DataFrame(logs).to_csv(OUT/'gameweek_log.csv',index=False)
        pd.DataFrame(plans).to_csv(OUT/'executed_plans.csv',index=False)
        print(f'GW{gw}: score={score} cum={total} tx={len(rows)} hit={hit}',flush=True)

    baseline=981
    summary={
      'classification':'PM(vFinal current GW)+TS(v4) hybrid integration diagnostic; GW22-38',
      'point_model_current_gw':'integrated vFinal',
      'future_horizon_model':'cutoff-frozen recovered Phase5Q for GW+1..GW+5',
      'no_future_vfinal_leakage':True,
      'chips':'OFF',
      'points_gw22_38':int(total),
      'reference_ts_v4_phase5q_gw22_38':baseline,
      'delta_vs_ts_v4_proxy':int(total-baseline),
      'transfers':int(sum(x['transfers'] for x in logs)),
      'hit_points':int(sum(x['hit_cost'] for x in logs)),
      'full_all_vfinal_rolling_replay':False,
      'next_requirement':'regenerate vFinal for all origin-target horizon cells before final PM+TS season claim'
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
