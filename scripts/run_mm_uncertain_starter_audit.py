#!/usr/bin/env python3
"""Targeted audit for uncertain starters in the unified Minute Model.

Tests whether recent start/non-start sequence should directly correct P(start)
on top of the unified MM. Selection uses GW16-21 only. GW22-38 is diagnostic.
If no candidate improves uncertain-starter xMins without an overall guardrail
violation, keep unified MM unchanged and emit a GW-by-GW failure audit.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from run_mm_unified_official_roles import (
    SOURCE,OUT as MM_OUT,build_role_games,add_importance,role_features,full_mm
)
from run_v4_performance_rating_experiment import fit_offset,build_perf_ledger,add_features as add_perf_features
from run_v4_three_state_sequence_experiment import (
    add_sequence_features,SEQ_FEATURES,metrics,write_gzip_csv,write_json
)

OUT=ROOT/'analysis/results/mm-uncertain-starters-20261006-v1'
L2=[0.5,2.0,10.0,40.0]
FAMILIES={
 'recent_start_state':[
   'seq_last_started','seq_start_share3','seq_start_share5',
   'seq_start_streak','seq_nonstart_streak','seq_changed_state_last'
 ],
 'recent_start_minutes':[
   'seq_last_started','seq_start_share3','seq_start_share5',
   'seq_start_streak','seq_nonstart_streak','seq_changed_state_last',
   'seq_last_minutes','seq_prev_minutes','seq_mean2_minutes','seq_mean3_minutes',
   'seq_trend_2_vs_prev3','seq_minutes_slope5'
 ],
}

def uncertain_metrics(frame,mask,p,q,xm):
    return metrics(frame,mask,p,q,xm)

def compose_with_p(frame,p,q,sub):
    return p*frame.start_minutes_mean.to_numpy(float)+(1-p)*q*np.asarray(sub,float)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base_result=json.loads((MM_OUT/'result.json').read_text())
    qs=float(base_result['selected_importance_weights']['q'])
    hs=float(base_result['selected_importance_weights']['H'])

    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    games,_,_=build_role_games();games=add_importance(games)
    frame=role_features(frame,games,qs,hs)

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev=frame.gw.between(16,21).to_numpy()
    cut=pd.to_datetime(frame.loc[dev,'cutoff'],utc=True).min()
    tr=(frame.gw.between(6,15)&(known<cut)).to_numpy()
    p0,q0,sub0,xm0,_=full_mm(frame,tr)
    udev=dev&(p0>=.2)&(p0<=.8)
    base_dev_all=metrics(frame,dev,p0,q0,xm0)
    base_dev_u=metrics(frame,udev,p0,q0,xm0)

    rows=[];models={}
    for fam,features in FAMILIES.items():
        for l2 in L2:
            p,m=fit_offset(frame,p0,tr,features,l2)
            xm=compose_with_p(frame,p,q0,sub0)
            allm=metrics(frame,dev,p,q0,xm)
            umask=dev&(p0>=.2)&(p0<=.8)
            um=metrics(frame,umask,p,q0,xm)
            rows.append({
              'candidate':fam,'l2':l2,
              'uncertain_n':um['n'],
              'uncertain_state_log_loss':um['state_log_loss'],
              'uncertain_xmins_mae':um['xmins_mae'],
              'uncertain_xmins_rmse':um['xmins_rmse'],
              'all_state_log_loss':allm['state_log_loss'],
              'all_xmins_mae':allm['xmins_mae'],
              'all_xmins_rmse':allm['xmins_rmse'],
              'delta_uncertain_mae':um['xmins_mae']-base_dev_u['xmins_mae'],
              'delta_uncertain_rmse':um['xmins_rmse']-base_dev_u['xmins_rmse'],
              'delta_all_mae':allm['xmins_mae']-base_dev_all['xmins_mae'],
              'delta_all_rmse':allm['xmins_rmse']-base_dev_all['xmins_rmse'],
              'delta_all_state_log_loss':allm['state_log_loss']-base_dev_all['state_log_loss'],
            })
            models[f'{fam}_l2_{l2:g}']=m
    cand=pd.DataFrame(rows).sort_values(['uncertain_xmins_rmse','uncertain_xmins_mae','all_xmins_rmse'])
    cand.to_csv(OUT/'development_candidates.csv',index=False)
    ok=cand[
      (cand.delta_uncertain_rmse<0)&
      (cand.delta_uncertain_mae<=0)&
      (cand.delta_all_rmse<=0.05)&
      (cand.delta_all_mae<=0.05)&
      (cand.delta_all_state_log_loss<=0.002)
    ]
    if len(ok):
        best=ok.iloc[0];selected=str(best.candidate);sell2=float(best.l2)
    else:
        selected='none';sell2=None

    test=frame.gw.between(22,38).to_numpy()
    cut2=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
    tr2=(frame.gw.between(6,21)&(known<cut2)).to_numpy()
    pbase,qbase,subbase,xbase,_=full_mm(frame,tr2)
    if selected=='none':
        pnew=pbase.copy();xnew=xbase.copy();model=None
    else:
        pnew,model=fit_offset(frame,pbase,tr2,FAMILIES[selected],sell2)
        xnew=compose_with_p(frame,pnew,qbase,subbase)

    base_all=metrics(frame,test,pbase,qbase,xbase)
    new_all=metrics(frame,test,pnew,qbase,xnew)
    ub=test&(pbase>=.2)&(pbase<=.8)
    base_u=metrics(frame,ub,pbase,qbase,xbase)
    new_u=metrics(frame,ub,pnew,qbase,xnew)

    # GW-by-GW: all + uncertain starters. Also count large misses.
    gwrows=[]
    for gw in range(22,39):
        gm=test&frame.gw.eq(gw).to_numpy()
        if not gm.any():continue
        for label,mask in [('all',gm),('uncertain',gm&(pbase>=.2)&(pbase<=.8))]:
            if not mask.any():continue
            for arm,p,x in [('unified',pbase,xbase),('uncertain_corrected',pnew,xnew)]:
                m=metrics(frame,mask,p,qbase,x)
                err=np.abs(np.asarray(x)[mask]-frame.minutes.to_numpy(float)[mask])
                gwrows.append({'gw':gw,'slice':label,'arm':arm,**m,
                  'large_miss_30plus':int((err>=30).sum()),
                  'large_miss_45plus':int((err>=45).sum())})
    gwd=pd.DataFrame(gwrows)
    gwd.to_csv(OUT/'metrics_by_gw.csv',index=False)

    # Biggest uncertain misses under the selected/final arm, with useful pre-match state.
    idx=np.flatnonzero(ub)
    misses=pd.DataFrame({
      'row':idx,
      'abs_error':np.abs(xnew[idx]-frame.minutes.to_numpy(float)[idx]),
      'signed_error':xnew[idx]-frame.minutes.to_numpy(float)[idx],
    }).sort_values('abs_error',ascending=False).head(250)
    cols=['fixture_uuid','team_id','gw','team','player','pos','minutes','expected_role',
          'seq_last_started','seq_last_minutes','seq_start_share3','seq_start_share5',
          'seq_start_streak','seq_nonstart_streak','seq_changed_state_last',
          'work_player_rest_days','work_minutes_7d','work_minutes_14d','role_h_fast','role_h_slow']
    for c in cols:
        if c in frame:misses[c]=frame.loc[misses.row,c].to_numpy()
    misses['base_p_start']=pbase[misses.row.to_numpy(int)]
    misses['final_p_start']=pnew[misses.row.to_numpy(int)]
    misses['base_xmins']=xbase[misses.row.to_numpy(int)]
    misses['final_xmins']=xnew[misses.row.to_numpy(int)]
    misses.drop(columns='row').to_csv(OUT/'largest_uncertain_misses.csv',index=False)

    # Aggregate diagnostic to identify when/where MM falls off.
    worst=[]
    ugw=gwd[(gwd.slice=='uncertain')&(gwd.arm=='uncertain_corrected')].copy()
    if len(ugw):
        ugw=ugw.sort_values('xmins_mae',ascending=False)
        worst=ugw[['gw','n','xmins_mae','xmins_rmse','state_log_loss','large_miss_30plus','large_miss_45plus']].head(8).to_dict(orient='records')

    result={
      'classification':'targeted uncertain-starter development test; GW22-38 reused diagnostic',
      'selected':selected,'selected_l2':sell2,
      'development':{'unified_all':base_dev_all,'unified_uncertain':base_dev_u,
                     'candidates':cand.to_dict(orient='records')},
      'reused_diagnostic':{
        'unified_all':base_all,'final_all':new_all,
        'unified_uncertain':base_u,'final_uncertain':new_u,
        'delta_all':{k:new_all[k]-base_all[k] for k in ['state_log_loss','state_brier','xmins_mae','xmins_rmse','xmins_bias']},
        'delta_uncertain':{k:new_u[k]-base_u[k] for k in ['state_log_loss','state_brier','xmins_mae','xmins_rmse','xmins_bias']},
      },
      'worst_uncertain_gameweeks':worst,
      'promotion_rule':'Only a development-selected candidate satisfying uncertain and overall guardrails is carried to reused diagnostic.',
      'mm_lock_recommendation':'lock corrected candidate' if selected!='none' else 'keep unified MM; inspect GW/player misses rather than add unproven complexity'
    }
    write_json(OUT/'result.json',result)
    write_json(OUT/'selected_model.json',{'selected':selected,'l2':sell2,'model':model})
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
