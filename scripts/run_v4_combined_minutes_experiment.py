#!/usr/bin/env python3
"""Combined exploratory minute model: performance P(start) + sequence substate + blended sub duration.

Fixed upstream choices from prior development experiments:
  * P(start): v4 + last-match performance residual, L2=0.5
  * P(sub|not start): sequence-aware binary model, C=4, 75% logit blend with v4 q
  * E[min|start]: frozen v4 starter duration
  * E[min|sub]: blend between frozen v4 cameo mean and sequence-aware sub-duration

Only the sub-duration blend weight (and ridge alpha among the already-tested
small grid) is selected here on GW16-21. GW22-38 remains a reused diagnostic.

This is a sequentially tuned exploratory candidate, not an independent holdout
result and not eligible for automatic promotion.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.special import expit, logit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.workload import WORKLOAD_FEATURES
from fpl_v1_1_model.minutes_decomposition import component_inputs
from run_v4rc_experiment import fit_v4_start
from run_v4_performance_rating_experiment import (
    SOURCE, build_perf_ledger, add_features as add_perf_features,
    fit_offset as fit_perf_offset, FAMILIES as PERF_FAMILIES
)
from run_v4_three_state_sequence_experiment import (
    SEQ_FEATURES, BASE_Q_FEATURES, add_sequence_features, fit_q, metrics,
    sha, write_json, write_gzip_csv
)
from run_v4_three_state_duration_experiment import fit_duration

OUT=ROOT/'analysis/results/v4-combined-minutes-20261005-v1'
PERF_L2=0.5
Q_C=4.0
Q_ALPHA=0.75
RIDGE_ALPHAS=[5.0,20.0,80.0]
SUB_BLEND=[0.0,0.25,0.5,0.75,1.0]


def compose(frame,p_start,q,sub_minutes):
    s=frame.start_minutes_mean.to_numpy(float)
    return p_start*s+(1-p_start)*q*np.asarray(sub_minutes,float)


def metric_with_start(frame,mask,p_start,q,xm):
    d=metrics(frame,mask,p_start,q,xm)
    y=frame.y.to_numpy(float)[mask]
    p=np.clip(np.asarray(p_start,float)[mask],1e-12,1-1e-12)
    d['start_brier']=float(np.mean((p-y)**2))
    d['start_log_loss']=float(-np.mean(y*np.log(p)+(1-y)*np.log1p(-p)))
    return d


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    OUT.mkdir(parents=True)

    protocol={
      'name':'combined v4 minute candidate',
      'components':{
        'p_start':'v4 + last-match performance residual, l2=0.5',
        'p_sub_given_nonstart':'sequence binary C=4, 75% logit blend with v4',
        'start_duration':'frozen v4',
        'sub_duration':'blend(frozen v4, sequence Ridge)'
      },
      'development_train':'GW6-15',
      'development_selection':'GW16-21; already reused by earlier exploratory steps',
      'final_train':'GW6-21',
      'reused_diagnostic':'GW22-38; not independent',
      'sub_duration_ridge_grid':RIDGE_ALPHAS,
      'sub_duration_blend_grid':SUB_BLEND,
      'selection':'lowest development xMins RMSE; ties within 0.01 prefer lower blend, then lower MAE',
      'promotion_allowed':False,
      'reason':'sequential development tuning; independent season/test required'
    }
    write_json(OUT/'protocol.json',protocol)

    frame=pd.read_csv(SOURCE).reset_index(drop=True)
    frame=add_sequence_features(frame)
    perf_ledger=build_perf_ledger()
    frame=add_perf_features(frame,perf_ledger)

    # materialize duration feature schema
    X=component_inputs(frame)
    for c in WORKLOAD_FEATURES+SEQ_FEATURES: X[c]=frame[c].to_numpy(float)
    dur_features=list(X.columns)
    for c in dur_features:
        if c not in frame: frame[c]=X[c]

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev=frame.gw.between(16,21).to_numpy()
    devcut=pd.to_datetime(frame.loc[dev,'cutoff'],utc=True).min()
    tr=(frame.gw.between(6,15)&(known<devcut)).to_numpy()

    # Baseline v4
    p_v4,_=fit_v4_start(frame,tr)
    q_v4=np.clip(frame.p_cameo_given_bench.to_numpy(float),1e-6,1-1e-6)
    sub_v4=frame.cameo_minutes_mean.to_numpy(float)
    xm_v4=compose(frame,p_v4,q_v4,sub_v4)
    base=metric_with_start(frame,dev,p_v4,q_v4,xm_v4)

    # Performance P(start)
    p_perf,perf_model=fit_perf_offset(frame,p_v4,tr,PERF_FAMILIES['last'],PERF_L2)

    # Sequence q
    q_hat,q_model=fit_q(frame,tr,BASE_Q_FEATURES+SEQ_FEATURES,Q_C)
    q_seq=expit((1-Q_ALPHA)*logit(q_v4)+Q_ALPHA*logit(np.clip(q_hat,1e-6,1-1e-6)))

    # Precompute sequence sub-duration predictions by ridge alpha.
    rows=[];sub_models={}
    for ridge in RIDGE_ALPHAS:
        sub_seq,sub_model=fit_duration(frame,tr,'sub',dur_features,ridge)
        sub_models[str(ridge)]=sub_model
        for a in SUB_BLEND:
            sub=(1-a)*sub_v4+a*sub_seq
            xm=compose(frame,p_perf,q_seq,sub)
            met=metric_with_start(frame,dev,p_perf,q_seq,xm)
            rows.append({'ridge_alpha':ridge,'sub_blend':a,**met,
                         'delta_xmins_mae_vs_v4':met['xmins_mae']-base['xmins_mae'],
                         'delta_xmins_rmse_vs_v4':met['xmins_rmse']-base['xmins_rmse'],
                         'delta_start_log_loss_vs_v4':met['start_log_loss']-base['start_log_loss'],
                         'delta_state_log_loss_vs_v4':met['state_log_loss']-base['state_log_loss']})
    cand=pd.DataFrame(rows).sort_values(['xmins_rmse','xmins_mae','sub_blend','ridge_alpha']).reset_index(drop=True)
    min_rmse=float(cand.xmins_rmse.min())
    near=cand[cand.xmins_rmse<=min_rmse+0.01].sort_values(['sub_blend','xmins_mae','ridge_alpha'])
    best=near.iloc[0]
    sel_ridge=float(best.ridge_alpha); sel_blend=float(best.sub_blend)
    cand.to_csv(OUT/'development_candidates.csv',index=False)

    selection={'v4':base,'selected_ridge_alpha':sel_ridge,'selected_sub_blend':sel_blend,
               'selected_development_metrics':{k:float(best[k]) for k in
                   ['start_brier','start_log_loss','state_brier','state_log_loss',
                    'sub_brier_given_nonstart','xmins_mae','xmins_rmse','xmins_bias']}}
    write_json(OUT/'selection.json',selection)
    write_json(OUT/'development_models.json',{'performance':perf_model,'q':q_model,'sub_duration':sub_models})

    # Final fit for reused diagnostic
    test=frame.gw.between(22,38).to_numpy()
    finalcut=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
    finaltr=(frame.gw.between(6,21)&(known<finalcut)).to_numpy()

    p_v4_f,_=fit_v4_start(frame,finaltr)
    p_perf_f,perf_model_f=fit_perf_offset(frame,p_v4_f,finaltr,PERF_FAMILIES['last'],PERF_L2)
    q_hat_f,q_model_f=fit_q(frame,finaltr,BASE_Q_FEATURES+SEQ_FEATURES,Q_C)
    q_seq_f=expit((1-Q_ALPHA)*logit(q_v4)+Q_ALPHA*logit(np.clip(q_hat_f,1e-6,1-1e-6)))
    sub_seq_f,sub_model_f=fit_duration(frame,finaltr,'sub',dur_features,sel_ridge)
    sub_f=(1-sel_blend)*sub_v4+sel_blend*sub_seq_f

    xm_base=compose(frame,p_v4_f,q_v4,sub_v4)
    xm_perf=compose(frame,p_perf_f,q_v4,sub_v4)
    xm_perf_seq=compose(frame,p_perf_f,q_seq_f,sub_v4)
    xm_comb=compose(frame,p_perf_f,q_seq_f,sub_f)

    arms={
      'v4':(p_v4_f,q_v4,xm_base),
      'performance_only':(p_perf_f,q_v4,xm_perf),
      'performance_plus_sequence_state':(p_perf_f,q_seq_f,xm_perf_seq),
      'combined':(p_perf_f,q_seq_f,xm_comb)
    }
    diag={k:metric_with_start(frame,test,*v) for k,v in arms.items()}
    diag['delta_combined_minus_v4']={m:diag['combined'][m]-diag['v4'][m] for m in
        ['start_brier','start_log_loss','state_brier','state_log_loss',
         'sub_brier_given_nonstart','xmins_mae','xmins_rmse','xmins_bias']}

    # Diagnostic slices
    state=np.where(frame.y.to_numpy(int)==1,2,np.where(frame.minutes.to_numpy(float)>0,1,0))
    pband=(p_v4_f>=.2)&(p_v4_f<=.8)
    changed=frame.seq_changed_state_last.to_numpy(float)>0.5
    groups=[
      ('all',test),('pstart_0.20_0.80',test&pband),
      ('sequence_changed',test&changed),
      ('strong_uptrend',test&(frame.seq_trend_2_vs_prev3.to_numpy()>=20)),
      ('strong_downtrend',test&(frame.seq_trend_2_vs_prev3.to_numpy()<=-20)),
      ('POSTHOC_starter',test&(state==2)),
      ('POSTHOC_substitute',test&(state==1)),
      ('POSTHOC_zero',test&(state==0))
    ]
    sr=[]
    for label,m in groups:
        if not m.any(): continue
        for arm,(p,q,xm) in arms.items():
            sr.append({'slice':label,'arm':arm,**metric_with_start(frame,m,p,q,xm)})
    pd.DataFrame(sr).to_csv(OUT/'diagnostic_slices.csv',index=False)

    # By GW stability
    gwrows=[]
    for gw in range(22,39):
        m=test&frame.gw.eq(gw).to_numpy()
        if not m.any(): continue
        for arm,(p,q,xm) in arms.items():
            gwrows.append({'gw':gw,'arm':arm,**metric_with_start(frame,m,p,q,xm)})
    pd.DataFrame(gwrows).to_csv(OUT/'metrics_by_gw.csv',index=False)

    pred=frame.loc[test,['fixture_uuid','team_id','player_uuid','gw','team','player','pos','expected_role','y','minutes']].copy()
    for arm,(p,q,xm) in arms.items():
        pred[f'{arm}_p_start']=p[test];pred[f'{arm}_q_sub']=q[test];pred[f'{arm}_xmins']=xm[test]
    pred['combined_sub_minutes']=sub_f[test]
    write_gzip_csv(pred,OUT/'reused_diagnostic_predictions.csv.gz')

    result={
      'classification':'combined exploratory minute candidate; sequentially tuned, reused diagnostic only',
      'development_selection':selection,
      'reused_diagnostic':diag,
      'selected_sub_duration':{'ridge_alpha':sel_ridge,'blend':sel_blend},
      'performance_proxy_rows':int(len(perf_ledger)),
      'promoted':False,
      'next_requirement':'independent season/time-split validation before freezing/promoting'
    }
    write_json(OUT/'result.json',result)
    write_json(OUT/'frozen_models.json',{'performance':perf_model_f,'q':q_model_f,'sub_duration':sub_model_f,
                                         'sub_blend':sel_blend})
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',{
      'sources':[{'path':str(SOURCE.relative_to(ROOT)),'sha256':sha(SOURCE)},
                 {'path':'scripts/run_v4_combined_minutes_experiment.py','sha256':sha(Path(__file__))}],
      'outputs':[{'path':p.name,'sha256':sha(p)} for p in outs]})
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
