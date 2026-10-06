#!/usr/bin/env python3
"""Full-season PM+TS warm-start replay.

Cutoff-safe structure:
- GW1-21: recovered rolling Phase5Q PM as warm-up proxy.
- Initial squad before GW1: new joint 6GW initial-squad optimizer on the
  cutoff-frozen GW1 Phase5Q horizon.
- GW22-38 current decision GW: integrated vFinal PM wherever identity mapping
  is exact; unresolved identities retain Phase5Q.
- Future GW+1..GW+5 horizon at every decision remains the recovered cutoff-
  frozen Phase5Q forecast. No later target-deadline vFinal is injected backwards.
- TS: joint rolling MILP, execute first action only, chips OFF.

This is the strongest leakage-safe full-season combined replay available with
the currently frozen artifacts. It is NOT an all-horizon rolling-vFinal replay.
"""
from __future__ import annotations
import json,sys,time,unicodedata
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT/'scripts'))

import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as base
from fpl_xpts.initial_squad_joint import InitialSquadConfig,optimize_initial_squad_joint
from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import (
    OwnedPlayer,ReplayState,actual_team_points,legalize_team_limit,valid_squad
)
from fpl_xpts.transfer_planner import execute_first_action
from fpl_xpts.transfer_planner_joint import JointPlannerConfig,plan_transfer_path_joint

VFINAL=ROOT/'analysis/results/vfinal-integrated-20261005-v1'
MINS=ROOT/'analysis/results/v4-combined-minutes-20261005-v1/reused_diagnostic_predictions.csv.gz'
OUT=ROOT/'analysis/results/pm-ts-vfinal-warmstart-fullseason-20261006-v1'
WEIGHTS=(1.00,.85,.70,.55,.40,.25)
BUFFER=1.5


def _norm_name(x):
    s=unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().casefold()
    return ''.join(ch for ch in s if ch.isalnum())


def mapping_uuid_to_id():
    feat=pd.read_csv(
        ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz',
        usecols=['player_uuid','player']
    ).drop_duplicates()
    raw=hp.unpack_runtime('players_raw.csv').drop_duplicates('id').copy()
    candidates={}
    for r in raw.itertuples():
        vals=[getattr(r,'web_name','')]
        first=getattr(r,'first_name',''); second=getattr(r,'second_name','')
        if str(first)!='nan' or str(second)!='nan':
            vals.append(f"{first} {second}")
        for v in vals:
            k=_norm_name(v)
            if k: candidates.setdefault(k,set()).add(int(r.id))
    out={}
    for r in feat.itertuples():
        ids=candidates.get(_norm_name(r.player),set())
        if len(ids)==1: out[str(r.player_uuid)]=next(iter(ids))
    return out


def vfinal_current_table():
    mp=mapping_uuid_to_id()
    p=pd.read_csv(VFINAL/'predictions.csv.gz')
    total_uuid=int(p.player_uuid.nunique())
    p['id']=p.player_uuid.astype(str).map(mp)
    p=p[p.id.notna()].copy(); p.id=p.id.astype(int)
    mapped_uuid=int(p.player_uuid.nunique())

    x=p.groupby(['gw','id'],as_index=False).agg(xpts_mean=('vfinal_xpts','sum'))
    m=pd.read_csv(MINS)
    m['id']=m.player_uuid.astype(str).map(mp)
    m=m[m.id.notna()].copy(); m.id=m.id.astype(int)
    m['p_play_fixture']=m.combined_p_start+(1-m.combined_p_start)*m.combined_q_sub
    play=m.groupby(['gw','id'],as_index=False).agg(
        p_no_play=('p_play_fixture',lambda s:float(np.prod(1-np.clip(s,0,1)))))
    play['p_play']=1-play.p_no_play
    return x.merge(play[['gw','id','p_play']],on=['gw','id'],how='left'), mapped_uuid,total_uuid


def planner_origin(forecast,meta,gw,vf):
    origin=base.origin_with_meta(forecast,meta,gw)
    if gw>=22:
        cur=vf[vf.gw==gw][['id','xpts_mean','p_play']].copy()
        origin=origin.merge(cur,on='id',how='left',suffixes=('','_vf'))
        now=origin.gw.eq(gw)
        origin.loc[now & origin.xpts_mean_vf.notna(),'xpts_mean']=origin.loc[now & origin.xpts_mean_vf.notna(),'xpts_mean_vf']
        origin.loc[now & origin.p_play_vf.notna(),'p_play']=origin.loc[now & origin.p_play_vf.notna(),'p_play_vf']
        origin=origin.drop(columns=['xpts_mean_vf','p_play_vf'])
    return origin


def current_projection(origin,meta,gw):
    stripped=origin.drop(columns=[
        c for c in ['meta_team','meta_price_tenths','meta_web_name','meta_position'] if c in origin.columns
    ])
    return hp.complete_current_projection(stripped,meta,gw)


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    gws,names,forecast=base.prepare()
    vf,mapped_uuid,total_uuid=vfinal_current_table()
    print(f'vFinal identity coverage: {mapped_uuid}/{total_uuid} UUIDs; unresolved rows retain Phase5Q',flush=True)

    # New joint six-GW opening squad on the only leakage-safe early-season
    # forecast archive currently available.
    meta1=hp.gw_meta(gws,names,1)
    origin1=base.origin_with_meta(forecast,meta1,1)
    init=optimize_initial_squad_joint(
        origin1,meta1,1,
        InitialSquadConfig(weights=WEIGHTS,budget_tenths=1000,time_limit=60,mip_rel_gap=.002)
    )
    price=meta1.set_index('id').price_tenths.astype(int)
    state=ReplayState(
        squad={pid:OwnedPlayer(pid,int(price[pid])) for pid in init.squad_ids},
        bank=int(init.bank_tenths),
        free_transfers=0,
    )
    initial=list(init.squad_ids)
    known=meta1.copy()
    total=0; logs=[]; plans=[]

    for gw in range(1,39):
        t0=time.perf_counter()
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin=planner_origin(forecast,meta,gw,vf)
        current=current_projection(origin,meta,gw)

        forced=[]; optional=[]; hit=0
        if gw==1:
            # Opening squad is locked through GW1 deadline. First FT is credited after GW1.
            state.free_transfers=1
        else:
            ft_before=int(state.free_transfers)
            forced=legalize_team_limit(state,meta,origin,gw)
            forced_n=len(forced)
            state.free_transfers=max(0,ft_before-forced_n)
            cfg=JointPlannerConfig(
                weights=WEIGHTS,hit_uncertainty_buffer=BUFFER,max_transfers_per_week=5,
                first_gw_max_transfers=max(0,5-forced_n),
                time_limit=60,mip_rel_gap=.002,retry_time_limit=180,retry_mip_rel_gap=.01
            )
            result=plan_transfer_path_joint(state,meta,origin,gw,cfg)
            optional=execute_first_action(state,result,meta)
            hit=sum(int(x.get('hit',0)) for x in forced)+sum(int(x.get('hit',0)) for x in optional)
            expected_hit=4*max(0,len(forced)+len(optional)-ft_before)
            if hit!=expected_hit:
                raise RuntimeError(f'GW{gw}: hit mismatch {hit} vs {expected_hit}')
            a=result.first_action
            for step,x in enumerate(result.path,1):
                plans.append(dict(
                    origin_gw=gw,step=step,target_gw=x.gw,is_executed=(step==1),
                    outgoing=';'.join(map(str,x.outgoing)),incoming=';'.join(map(str,x.incoming)),
                    transfers=x.transfers,official_hit_points=x.official_hit_points,
                    free_transfers_before=x.free_transfers_before,free_transfers_after=x.free_transfers_after,
                    bank_before=x.bank_before/10,bank_after=x.bank_after/10,
                    projected_manager_score=x.projected_manager_score,objective=float(result.objective)
                ))

        if not valid_squad(meta,state.squad): raise RuntimeError(f'GW{gw}: invalid squad')
        if state.bank<0: raise RuntimeError(f'GW{gw}: negative bank')

        plan=plan_squad(current,list(state.squad),gw)
        score,_=actual_team_points(plan.rows,hp.actual_gw(gws,gw),None,hit)
        total+=score
        logs.append(dict(
            gw=gw,score=int(score),cumulative=int(total),
            pm_current='vFinal' if gw>=22 else 'Phase5Q_warmup',
            transfers=int(len(forced)+len(optional)),forced_transfers=int(len(forced)),
            hit_points=int(hit),bank=state.bank/10,free_transfers_after=int(state.free_transfers),
            runtime_seconds=float(time.perf_counter()-t0)
        ))
        pd.DataFrame(logs).to_csv(OUT/'gameweek_log.csv',index=False)
        pd.DataFrame(plans).to_csv(OUT/'plans.csv',index=False)
        print(
            f"GW{gw}: PM={'vFinal' if gw>=22 else 'warmup'} score={score} cum={total} "
            f"tx={len(forced)+len(optional)} hit={hit}",
            flush=True
        )

    summary={
      'classification':'leakage-safe PM+TS full-season warm-start replay',
      'total_points':int(total),
      'points_gw1_21':int(sum(x['score'] for x in logs if x['gw']<=21)),
      'points_gw22_38':int(sum(x['score'] for x in logs if x['gw']>=22)),
      'transfers':int(sum(x['transfers'] for x in logs)),
      'hit_points':int(sum(x['hit_points'] for x in logs)),
      'initial_squad_optimizer':'joint 6GW MILP',
      'initial_pm':'Phase5Q cold/warm-start proxy',
      'pm_gw1_21':'Phase5Q rolling warm-up',
      'pm_current_gw22_38':'integrated vFinal where identity mapped',
      'future_horizon_all_gws':'cutoff-frozen Phase5Q',
      'vfinal_identity_coverage':{'mapped_uuid':mapped_uuid,'total_uuid':total_uuid,'share':mapped_uuid/total_uuid},
      'chips':'OFF',
      'no_target_deadline_vfinal_backfill':True,
      'warning':'Not an all-horizon rolling-vFinal replay; final all-vFinal origin-target builder remains future work.',
      'references':{'ts_v4_phase5q_fullseason':2120,'ts_v2_proxy':2137}
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
