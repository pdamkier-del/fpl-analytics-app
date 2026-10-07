#!/usr/bin/env python3
"""Conditional 2024/25 TS v3 robustness replay from GW6 to GW38.

Starts a fresh legal 15-player squad at GW6 from the locked vFinal forecast and
then runs the unchanged TS v3 planner through GW38. This deliberately does not
invent a GW1-5 cold-start provider that is absent from the historical checkpoint.

Forecast/model parameters are frozen. Historical deadline roster/price snapshots
are conditional proxies because their capture clocks are not independently
certified. Chips are OFF.
"""
from __future__ import annotations
import argparse,gzip,json,sys,time
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_horizon_policy_comparison as hp
from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import OwnedPlayer,ReplayState,actual_team_points,initial_squad,legalize_team_limit,valid_squad
from fpl_xpts.transfer_planner import PlannerConfig,execute_first_action,plan_transfer_path

WEIGHTS=(1.0,.60,.36,.216,.1296,.07776)
BUFFER=1.0
POS={1:'GKP',2:'DEF',3:'MID',4:'FWD','1':'GKP','2':'DEF','3':'MID','4':'FWD'}

def jsonl(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return [json.loads(x) for x in f if x.strip()]

def runtime_inputs(derived):
    actual=pd.read_csv(derived/'eligible_player_fixture_actuals.csv.gz',low_memory=False)
    if 'gw' not in actual and 'GW' in actual:actual['gw']=actual.GW
    snaps=jsonl(derived/'deadline_player_candidates.jsonl.gz')
    meta=pd.DataFrame([dict(gw=int(r['gw']),element=int(r['fpl_element']),team=int(r['team_id']),
        position=POS.get(r.get('fpl_position'),str(r.get('fpl_position'))),value=int(r.get('price_tenths') or 0),
        web_name=str(r.get('web_name') or r.get('player_name') or r['fpl_element']))
        for r in snaps if r.get('fpl_element') is not None])
    meta=meta.drop_duplicates(['gw','element'],keep='last')
    names=meta.sort_values('gw').drop_duplicates('element',keep='last').set_index('element').web_name.to_dict()
    z=actual.copy()
    z['element']=pd.to_numeric(z.element,errors='coerce').astype('Int64')
    z=z[z.element.notna()].copy();z.element=z.element.astype(int)
    z=z.merge(meta,on=['gw','element'],how='left',validate='many_to_one',suffixes=('','_deadline'))
    for col in ['team','position','value']:
        dcol=col+'_deadline'
        if dcol in z.columns:z[col]=z[dcol]
    if z[['team','position','value']].isna().any().any():
        # Conditional snapshots are expected to cover the active FPL cohort.
        miss=z[z[['team','position','value']].isna().any(axis=1)][['gw','element']].drop_duplicates()
        raise ValueError('Missing conditional deadline metadata: '+str(miss.head(20).to_dict('records')))
    z=z.rename(columns={'gw':'GW'})
    keep=['GW','element','team','position','value','total_points','minutes']
    return z[keep].copy(),names

def origin_with_meta(forecast,meta,gw):
    origin=forecast[forecast.origin_gw==gw-1].copy()
    mm=meta[['id','team','price_tenths']].rename(columns={'team':'meta_team','price_tenths':'meta_price_tenths'})
    origin=origin.merge(mm,on='id',how='left')
    if 'team' not in origin:origin['team']=origin.meta_team
    else:origin['team']=origin.team.fillna(origin.meta_team)
    origin['price_tenths']=origin.meta_price_tenths
    return origin

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--derived',required=True);ap.add_argument('--vfinal',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--start-gw',type=int,default=6);ap.add_argument('--end-gw',type=int,default=38)
    a=ap.parse_args();derived=Path(a.derived);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names=runtime_inputs(derived)
    forecast=pd.read_csv(a.vfinal);forecast.id=forecast.id.astype(int)
    forecast['web_name']=forecast.id.map(names).fillna(forecast.id.astype(str))
    keep=['id','web_name','position','gw','origin_gw','xpts_mean','p_play','fixtures','team']
    for c in keep:
        if c not in forecast:
            if c=='team':forecast[c]=pd.NA
            else:raise ValueError('Missing forecast column '+c)
    forecast=forecast[keep].copy()
    if not (6<=a.start_gw<=a.end_gw<=38):raise ValueError('Expected 6 <= start-gw <= end-gw <= 38')
    missing=[g for g in range(a.start_gw,a.end_gw+1) if not (forecast.origin_gw==g-1).any()]
    if missing:raise ValueError('Missing PM origins '+str(missing))

    meta=hp.gw_meta(gws,names,a.start_gw)
    origin0=hp.complete_current_projection(forecast[forecast.origin_gw==a.start_gw-1],meta,a.start_gw)
    state=initial_squad(origin0,meta,[a.start_gw]);initial=list(state.squad)
    total=0;control=0;logs=[];plans=[]
    config=PlannerConfig(weights=WEIGHTS,hit_uncertainty_buffer=BUFFER,beam_width=20,
        candidates_per_transfer_count=1,candidate_limit_per_position=18,top_targets_per_position=18,
        local_bundle_beam=60,candidate_return_per_depth=12,max_transfers_per_week=5,
        candidate_backend='fast_local',milp_time_limit=2.0)

    known=meta.copy()
    for gw in range(a.start_gw,a.end_gw+1):
        t0=time.perf_counter()
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin_raw=forecast[forecast.origin_gw==gw-1].copy()
        current=hp.complete_current_projection(origin_raw,meta,gw)
        origin=origin_with_meta(forecast,meta,gw)
        forced=[]
        if gw>a.start_gw:forced=legalize_team_limit(state,meta,origin,gw)
        result=plan_transfer_path(state,meta,origin,gw,config)
        transfers=execute_first_action(state,result,meta)
        hit_cost=sum(int(x.get('hit',0)) for x in transfers)+sum(int(x.get('hit',0)) for x in forced)
        if not valid_squad(meta,state.squad):raise RuntimeError(f'GW{gw}: invalid squad')
        plan=plan_squad(current,list(state.squad),gw)
        score,_=actual_team_points(plan.rows,hp.actual_gw(gws,gw),None,hit_cost);total+=score
        cp=plan_squad(current,initial,gw);cs,_=actual_team_points(cp.rows,hp.actual_gw(gws,gw),None,0);control+=cs
        logs.append(dict(gw=gw,score=score,cumulative=total,transfers=len(transfers)+len(forced),
            forced_transfers=len(forced),hit_cost=hit_cost,bank=state.bank/10,
            free_transfers_after=state.free_transfers,planner_objective=result.objective,
            runtime_seconds=time.perf_counter()-t0))
        for step,x in enumerate(result.path,1):
            plans.append(dict(origin_gw=gw,step=step,target_gw=x.gw,transfers=x.transfers,
                outgoing=';'.join(map(str,x.outgoing)),incoming=';'.join(map(str,x.incoming)),
                official_hit_points=x.official_hit_points,uncertainty_penalty=x.uncertainty_penalty,
                projected_manager_score=x.projected_manager_score,utility_this_gw=x.utility_this_gw,
                free_transfers_before=x.free_transfers_before,free_transfers_after=x.free_transfers_after,
                bank_before=x.bank_before/10,bank_after=x.bank_after/10,is_executed=(step==1)))
        print(f'GW{gw}: {score} pts cumulative {total}',flush=True)

    log=pd.DataFrame(logs);log.to_csv(out/'gameweek_log.csv',index=False);pd.DataFrame(plans).to_csv(out/'plans.csv',index=False)
    summary=dict(classification='CONDITIONAL_ROBUSTNESS_TS_GW6_38_NOT_FULL_SEASON',season='2024-25',
      start_gw=int(a.start_gw),end_gw=int(a.end_gw),initialization=f'fresh optimized GW{a.start_gw} squad from locked conditional vFinal forecast',
      weights=list(WEIGHTS),hit_uncertainty_buffer=BUFFER,chips='OFF',ts_v3_mechanics='unchanged planner/search mechanics',
      total_points_window=int(total),transfers=int(log.transfers.sum()),hit_points=int(log.hit_cost.sum()),
      no_transfer_control_window=int(control),uplift_vs_no_transfer_control=int(total-control),
      conditional_metadata='deadline price/team/position snapshots have unverified historical capture clocks',
      cold_start_gw1_5='NOT SCORED; no equivalent historical locked cold-start provider was available')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
