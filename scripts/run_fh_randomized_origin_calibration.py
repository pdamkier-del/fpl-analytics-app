#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from dataclasses import replace
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_transfer_strategy_v3_replay as ts
import run_horizon_policy_comparison as hp
from fpl_xpts.chip_planner import optimize_free_hit_squad
from fpl_xpts.fh_transfer_planner import _state_before_target
from fpl_xpts.season_replay import initial_squad,legalize_team_limit
from fpl_xpts.transfer_planner import PlannerConfig,plan_transfer_path,execute_first_action,clone_state

WEIGHTS=(1.0,.60,.36,.216,.1296,.07776)
BUFFER=1.0

def cfg():
    return PlannerConfig(weights=WEIGHTS,hit_uncertainty_buffer=BUFFER,beam_width=20,
        candidates_per_transfer_count=1,candidate_limit_per_position=18,
        top_targets_per_position=18,local_bundle_beam=60,candidate_return_per_depth=12,
        max_transfers_per_week=5,candidate_backend='fast_local',milp_time_limit=2.0)

def load_forecast(vfinal):
    gws,names,cold=ts.prepare()
    cold=cold[cold.origin_gw<=4].copy()
    vf=pd.read_csv(vfinal)
    vf['web_name']=vf.id.astype(int).map(names).fillna(vf.id.astype(str))
    keep=['id','web_name','position','gw','origin_gw','xpts_mean','p_play','fixtures']
    vf=vf[keep].copy();vf.id=vf.id.astype(int)
    forecast=pd.concat([cold[keep],vf],ignore_index=True)
    return gws,names,forecast

def baseline_states(gws,names,forecast):
    meta1=hp.gw_meta(gws,names,1)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    state=initial_squad(origin1,meta1,[1])
    known=meta1.copy();states={}
    pcfg=cfg()
    for gw in range(1,39):
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin=ts.origin_with_meta(forecast,meta,gw)
        if gw>1: legalize_team_limit(state,meta,origin,gw)
        states[gw]=(clone_state(state),meta.copy())
        result=plan_transfer_path(state,meta,origin,gw,pcfg)
        execute_first_action(state,result,meta)
    return states

def forecast_fh_panel(gws,names,forecast,states,seed):
    rng=np.random.default_rng(seed)
    origins=np.array(list(range(6,39)),dtype=int)
    rng.shuffle(origins)
    rows=[];pcfg=cfg()
    for ix,gw in enumerate(origins,1):
        state,meta=states[int(gw)]
        origin=ts.origin_with_meta(forecast,meta,int(gw))
        result=plan_transfer_path(state,meta,origin,int(gw),pcfg)
        action_by_gw={int(a.gw):a for a in result.path}
        for target in result.horizon_gws:
            target=int(target)
            a=action_by_gw[target]
            before=_state_before_target(state,result,meta,target)
            normal_net=float(a.projected_manager_score)-float(a.official_hit_points)
            fh=optimize_free_hit_squad(
                state=before,meta=meta,forecast=origin,gw=target,normal_score=normal_net,
            )
            rows.append(dict(origin_gw=int(gw),target_gw=target,horizon=target-int(gw),
                             fh_gain=float(fh['fh_gain']),fh_score=float(fh['fh_score']),
                             normal_score=float(normal_net),budget_tenths=int(fh['budget_tenths'])))
        print(f'origin {gw}: {len(result.horizon_gws)} FH horizons ({ix}/{len(origins)})',flush=True)
    return pd.DataFrame(rows)

def metrics(panel):
    ref=(panel[panel.horizon.eq(0)][['target_gw','fh_gain']]
         .rename(columns={'fh_gain':'ref_fh_gain'}))
    x=panel.merge(ref,on='target_gw',how='inner',validate='many_to_one')
    rows=[]
    for k,g in x.groupby('horizon',sort=True):
        if len(g)<8: continue
        a=g.fh_gain.astype(float);b=g.ref_fh_gain.astype(float)
        corr=float(a.corr(b,method='pearson')) if a.std()>1e-9 and b.std()>1e-9 else np.nan
        spear=float(a.corr(b,method='spearman')) if a.std()>1e-9 and b.std()>1e-9 else np.nan
        mae=float(np.mean(np.abs(a-b)))
        rmse=float(np.sqrt(np.mean((a-b)**2)))
        slope=float(np.cov(a,b,ddof=0)[0,1]/np.var(b)) if np.var(b)>1e-12 else np.nan
        rel=float(np.sqrt(max(0.0,corr)*max(0.0,spear))) if np.isfinite(corr) and np.isfinite(spear) else np.nan
        rows.append(dict(horizon=int(k),n=int(len(g)),pearson=corr,spearman=spear,
                         slope=slope,mae=mae,rmse=rmse,reliability=rel))
    return pd.DataFrame(rows),x

def fit_rho(m):
    z=m[(m.horizon>0)&m.reliability.notna()].copy()
    if z.empty: raise ValueError('no non-zero reliability horizons')
    k=z.horizon.to_numpy(float);r=np.clip(z.reliability.to_numpy(float),1e-6,1.0)
    log_rho=float(np.sum(k*np.log(r))/np.sum(k*k))
    rho=float(np.exp(log_rho))
    pred=np.power(rho,k)
    return rho,float(np.sqrt(np.mean((pred-r)**2)))

def bootstrap_rho(joined,n_boot,seed):
    rng=np.random.default_rng(seed+1);vals=[]
    targets=np.array(sorted(joined.target_gw.unique()),dtype=int)
    for _ in range(int(n_boot)):
        draw=rng.choice(targets,size=len(targets),replace=True)
        parts=[]
        for j,t in enumerate(draw):
            q=joined[joined.target_gw.eq(int(t))].copy();q['_boot_target']=j;parts.append(q)
        b=pd.concat(parts,ignore_index=True)
        rows=[]
        for k,g in b.groupby('horizon'):
            if int(k)==0 or len(g)<8: continue
            a=g.fh_gain.astype(float);r=g.ref_fh_gain.astype(float)
            if a.std()<=1e-9 or r.std()<=1e-9: continue
            p=float(a.corr(r,method='pearson'));s=float(a.corr(r,method='spearman'))
            rows.append(dict(horizon=int(k),reliability=float(np.sqrt(max(0,p)*max(0,s)))))
        if rows:
            try: vals.append(fit_rho(pd.DataFrame(rows))[0])
            except ValueError: pass
    arr=np.asarray(vals,float)
    return dict(n=int(len(arr)),mean=float(np.mean(arr)),median=float(np.median(arr)),
                p025=float(np.quantile(arr,.025)),p975=float(np.quantile(arr,.975)),
                p10=float(np.quantile(arr,.10)),p90=float(np.quantile(arr,.90)))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--vfinal',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--seed',type=int,default=20261008);ap.add_argument('--bootstrap',type=int,default=1000)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names,forecast=load_forecast(a.vfinal)
    states=baseline_states(gws,names,forecast)
    panel=forecast_fh_panel(gws,names,forecast,states,a.seed)
    hm,joined=metrics(panel)
    rho,fit_rmse=fit_rho(hm)
    boot=bootstrap_rho(joined,a.bootstrap,a.seed)
    hm['fitted_reliability']=np.power(rho,hm.horizon)
    hm['fit_error']=hm.reliability-hm.fitted_reliability
    panel.to_csv(out/'fh_randomized_origin_panel.csv',index=False)
    joined.to_csv(out/'fh_randomized_origin_joined.csv',index=False)
    hm.to_csv(out/'fh_reliability_curve.csv',index=False)
    summary={
      'classification':'Randomized-origin FH forecast reliability calibration',
      'baseline':'authoritative locked 2025/26 MM+PM/vFinal+TS no-chip path (2125-point artifact)',
      'objective':'estimate FH forecast-information decay only; no realised season points enter rho selection',
      'seed':int(a.seed),'origins':list(map(int,sorted(panel.origin_gw.unique()))),
      'origin_evaluation_order_randomized':True,'max_horizon':int(panel.horizon.max()),
      'rho_fh':float(rho),'fit_rmse':float(fit_rmse),'bootstrap':boot,
      'reliability_curve':hm.to_dict('records'),
      'method':'At each randomized origin, project the locked no-chip TS path, compute raw FH marginal gain for each visible target GW, and compare it with the same target GW forecast when that GW becomes current. Reliability=sqrt(Pearson*Spearman); fit R(k)=rho_FH^k.',
      'caveat':'Within one season this estimates forecast stability, not cross-season transportability. It deliberately avoids choosing rho by realised FPL points.'
    }
    (out/'summary.json').write_text(json.dumps(summary,indent=2,default=str)+'\n')
    print(json.dumps(summary,indent=2,default=str))

if __name__=='__main__': main()
