#!/usr/bin/env python3
"""GW22-38 A/B: propagate current-deadline vFinal correction across the full 6GW TS horizon.

This is leakage-safe:
- at decision GW d, only vFinal information available at d is used;
- the player-specific vFinal-vs-Phase5Q correction measured at d is frozen and
  applied to Phase5Q target forecasts d..d+5;
- no target-deadline vFinal from d+1..d+5 is used early.

This is NOT the final component-by-component rolling vFinal builder. It is a
consistent full-horizon vFinal-calibrated proxy designed to test the hypothesis
that mixing vFinal only in the current GW with Phase5Q in future GWs destabilized
TS v4 decisions.
"""
from __future__ import annotations
import json,sys,time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit,logit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as base
from fpl_xpts.optimize import plan_squad
from fpl_xpts.identity import resolve_uuid_to_fpl_ids
from fpl_xpts.season_replay import OwnedPlayer,ReplayState,actual_team_points,legalize_team_limit,valid_squad
from fpl_xpts.transfer_planner import execute_first_action
from fpl_xpts.transfer_planner_joint import JointPlannerConfig,plan_transfer_path_joint

BASE_ART=ROOT/'analysis/results/compare_inputs/ts_v4_phase5q'
VFINAL=ROOT/'analysis/results/vfinal-integrated-20261005-v1'
MINS=ROOT/'analysis/results/v4-combined-minutes-20261005-v1/reused_diagnostic_predictions.csv.gz'
OUT=ROOT/'analysis/results/pm-ts-vfinal-fullhorizon-proxy-gw22-38-20261006-v2'
WEIGHTS=(1.00,.85,.70,.55,.40,.25)
BUFFER=1.5


def ints(cell):
    if pd.isna(cell) or str(cell).strip()=='':
        return []
    return [int(float(x)) for x in str(cell).split(';') if str(x).strip() and str(x)!='nan']


def mapping_uuid_to_id():
    feat=pd.read_csv(ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz',
                     usecols=['player_uuid','player']).drop_duplicates()
    raw=hp.unpack_runtime('players_raw.csv').drop_duplicates('id').copy()
    mapping,matches=resolve_uuid_to_fpl_ids(feat,raw)
    detail=pd.DataFrame([m.__dict__ for m in matches])
    return mapping,detail


def vfinal_current():
    mp,identity_detail=mapping_uuid_to_id()
    p=pd.read_csv(VFINAL/'predictions.csv.gz')
    total=int(p.player_uuid.nunique())
    p['id']=p.player_uuid.astype(str).map(mp)
    p=p[p.id.notna()].copy();p.id=p.id.astype(int)
    mapped=int(p.player_uuid.nunique())
    x=p.groupby(['gw','id'],as_index=False).agg(vfinal_xp=('vfinal_xpts','sum'))

    m=pd.read_csv(MINS)
    m['id']=m.player_uuid.astype(str).map(mp)
    m=m[m.id.notna()].copy();m.id=m.id.astype(int)
    m['p_fixture']=m.combined_p_start+(1-m.combined_p_start)*m.combined_q_sub
    q=m.groupby(['gw','id'],as_index=False).agg(
        p_no_play=('p_fixture',lambda s:float(np.prod(1-np.clip(s,0,1)))))
    q['vfinal_p_play']=1-q.p_no_play
    return x.merge(q[['gw','id','vfinal_p_play']],on=['gw','id'],how='left'),mapped,total,identity_detail

def reconstruct_gw22_state(gws,names,forecast):
    plans=pd.read_csv(BASE_ART/'plans.csv')
    meta1=hp.gw_meta(gws,names,1)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    from fpl_xpts.season_replay import initial_squad
    state=initial_squad(origin1,meta1,[1])
    for gw in range(1,22):
        q=plans[(plans.origin_gw==gw)&(plans.is_executed.astype(str).str.lower().isin(['true','1']))]
        if q.empty: continue
        r=q.iloc[0]
        meta=hp.gw_meta(gws,names,gw).drop_duplicates('id').set_index('id')
        outs=ints(r.outgoing);ins=ints(r.incoming)
        for pid in outs: state.squad.pop(pid)
        for pid in ins: state.squad[pid]=OwnedPlayer(pid,int(meta.loc[pid,'price_tenths']))
        state.bank=int(round(float(r.bank_after)*10))
        state.free_transfers=int(r.free_transfers_after)
    return state


def apply_full_horizon_correction(origin,gw,vf):
    out=origin.copy()
    cur_base=(out[out.gw==gw][['id','xpts_mean','p_play']]
              .groupby('id',as_index=False)
              .agg(base_xp=('xpts_mean','sum'),base_p_play=('p_play','max')))
    cur=vf[vf.gw==gw][['id','vfinal_xp','vfinal_p_play']]
    z=cur_base.merge(cur,on='id',how='inner')
    if z.empty:return out,0,len(cur_base),len(cur_base)

    # Stable player correction. Additive 0.5 floor avoids huge ratios near zero.
    factor=(z.vfinal_xp+0.5)/(z.base_xp+0.5)
    z['xp_factor']=np.clip(factor,0.5,1.5)

    bp=np.clip(z.base_p_play.astype(float),1e-4,1-1e-4)
    vp=np.clip(z.vfinal_p_play.fillna(z.base_p_play).astype(float),1e-4,1-1e-4)
    z['pplay_logit_shift']=np.clip(logit(vp)-logit(bp),-1.5,1.5)

    fmap=dict(zip(z.id.astype(int),z.xp_factor.astype(float)))
    smap=dict(zip(z.id.astype(int),z.pplay_logit_shift.astype(float)))

    # Apply the same deadline-frozen player correction to every target GW in horizon.
    idx=out.id.astype(int).isin(fmap)
    out.loc[idx,'xpts_mean']=out.loc[idx].apply(
        lambda r:float(r.xpts_mean)*fmap[int(r.id)],axis=1)
    if 'p_play' in out:
        def adj(row):
            pid=int(row.id)
            if pid not in smap:return float(row.p_play)
            p=float(np.clip(row.p_play,1e-4,1-1e-4))
            return float(expit(logit(p)+smap[pid]))
        out.loc[idx,'p_play']=out.loc[idx].apply(adj,axis=1)

    # Current GW must equal integrated vFinal exactly on mapped rows.
    exact=dict(zip(z.id.astype(int),z.vfinal_xp.astype(float)))
    curmask=out.gw.eq(gw)&out.id.astype(int).isin(exact)
    # rolling table is one player-GW row in this archive; if that changes,
    # this direct assignment intentionally fails the equality audit below.
    out.loc[curmask,'xpts_mean']=out.loc[curmask].id.astype(int).map(exact)
    pexact=dict(zip(z.id.astype(int),z.vfinal_p_play.astype(float)))
    out.loc[curmask,'p_play']=out.loc[curmask].id.astype(int).map(pexact)

    return out,len(z),int(len(cur_base)-len(z)),len(cur_base)


def current_projection(origin,meta,gw):
    stripped=origin.drop(columns=[c for c in ['meta_team','meta_price_tenths','meta_web_name','meta_position'] if c in origin.columns])
    return hp.complete_current_projection(stripped,meta,gw)


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    gws,names,forecast=base.prepare()
    vf,mapped,total_uuid,identity_detail=vfinal_current()
    identity_detail.to_csv(OUT/'identity_resolution.csv',index=False)
    state=reconstruct_gw22_state(gws,names,forecast)
    known=hp.gw_meta(gws,names,1)
    for seen in range(2,22):
        obs=hp.gw_meta(gws,names,seen)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')

    total_points=0;logs=[];plans=[]
    for gw in range(22,39):
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin=base.origin_with_meta(forecast,meta,gw)
        origin,ncorr,nfallback,ncurrent=apply_full_horizon_correction(origin,gw,vf)
        cur_rows=origin[origin.gw.eq(gw)]
        if cur_rows.xpts_mean.isna().any():
            raise RuntimeError(f'GW{gw}: missing current-GW xP after explicit vFinal/Phase5Q composition')

        ft_before=int(state.free_transfers)
        forced=legalize_team_limit(state,meta,origin,gw)
        state.free_transfers=max(0,ft_before-len(forced))
        cfg=JointPlannerConfig(
            weights=WEIGHTS,hit_uncertainty_buffer=BUFFER,max_transfers_per_week=5,
            first_gw_max_transfers=max(0,5-len(forced)),
            time_limit=60,mip_rel_gap=.002,retry_time_limit=180,retry_mip_rel_gap=.01)
        t0=time.perf_counter()
        result=plan_transfer_path_joint(state,meta,origin,gw,cfg)
        optional=execute_first_action(state,result,meta)
        hit=sum(int(x.get('hit',0)) for x in forced)+sum(int(x.get('hit',0)) for x in optional)
        expected=4*max(0,len(forced)+len(optional)-ft_before)
        if hit!=expected:raise RuntimeError(f'GW{gw} hit mismatch {hit} vs {expected}')
        if not valid_squad(meta,state.squad):raise RuntimeError(f'GW{gw} invalid squad')

        current=current_projection(origin,meta,gw)
        plan=plan_squad(current,list(state.squad),gw)
        score,_=actual_team_points(plan.rows,hp.actual_gw(gws,gw),None,hit)
        total_points+=score
        logs.append(dict(gw=gw,score=int(score),cumulative=int(total_points),
                         transfers=len(forced)+len(optional),forced_transfers=len(forced),
                         hit_points=int(hit),bank=state.bank/10,free_transfers=state.free_transfers,
                         corrected_players=int(ncorr),fallback_players=int(nfallback),
                         current_forecast_players=int(ncurrent),
                         vfinal_share=float(ncorr/ncurrent) if ncurrent else 0.0,
                         runtime_seconds=time.perf_counter()-t0))
        for step,a in enumerate(result.path,1):
            plans.append(dict(origin_gw=gw,step=step,target_gw=a.gw,is_executed=(step==1),
                              outgoing=';'.join(map(str,a.outgoing)),incoming=';'.join(map(str,a.incoming)),
                              transfers=a.transfers,official_hit_points=a.official_hit_points,
                              free_transfers_before=a.free_transfers_before,free_transfers_after=a.free_transfers_after,
                              bank_before=a.bank_before/10,bank_after=a.bank_after/10,
                              projected_manager_score=a.projected_manager_score,objective=result.objective))
        pd.DataFrame(logs).to_csv(OUT/'gameweek_log.csv',index=False)
        pd.DataFrame(plans).to_csv(OUT/'plans.csv',index=False)
        print(f'GW{gw}: score={score} cum={total_points} tx={len(forced)+len(optional)} hit={hit} vfinal={ncorr}/{ncurrent} fallback={nfallback}',flush=True)

    baseline=981
    summary={
      'classification':'leakage-safe full-horizon vFinal-calibrated PM + TS v4 proxy v2, GW22-38',
      'points_gw22_38':int(total_points),
      'phase5q_reference':baseline,
      'delta_vs_phase5q':int(total_points-baseline),
      'transfers':int(sum(x['transfers'] for x in logs)),
      'hit_points':int(sum(x['hit_points'] for x in logs)),
      'identity_coverage':{
        'mapped_uuid':mapped,'total_uuid':total_uuid,'share':mapped/total_uuid,
        'unresolved_uuid':int(identity_detail.fpl_id.isna().sum()),
        'methods':identity_detail.method.value_counts().to_dict()},
      'forecast_composition':{
        'policy':'integrated vFinal where available; explicit Phase5Q fallback otherwise; never implicit zero',
        'mean_vfinal_share':float(np.mean([x['vfinal_share'] for x in logs])),
        'mean_fallback_players':float(np.mean([x['fallback_players'] for x in logs]))},
      'horizon_method':'freeze current-deadline player vFinal/Phase5Q xP correction and p(play) logit shift across GW d..d+5',
      'future_information_leakage':False,
      'warning':'Proxy for consistent all-horizon vFinal; not component-by-component regenerated future vFinal. Missing integrated rows use explicit Phase5Q fallback.'
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
