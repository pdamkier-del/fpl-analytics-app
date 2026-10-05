#!/usr/bin/env python3
"""v4-3S-v3: sequence-aware substate plus conditional-duration audit.

This follows the already development-selected v4-3S-v2 candidate:
  * P(start) = frozen v4 exactly
  * q=P(sub appearance|not start) = binary_sequence C=4 blended 75% on logit scale

Now test whether the remaining minute error is conditional-duration error,
especially around recent state transitions. Only duration models vary here.

Important: GW16-21 has already been used for prior model decisions. This is an
exploratory development iteration, not independent confirmation. GW22-38 also
remains a reused diagnostic. No app promotion is allowed from this experiment.
"""
from __future__ import annotations
import gzip, hashlib, io, json, os
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.workload import WORKLOAD_FEATURES
from fpl_v1_1_model.minutes_decomposition import component_inputs
from run_v4rc_experiment import fit_v4_start
from run_v4_three_state_sequence_experiment import (
    SOURCE,V4_RESULTS,SEQ_FEATURES,BASE_Q_FEATURES,add_sequence_features,
    fit_q,compose,metrics,sha,write_json,write_gzip_csv
)

OUT=ROOT/'analysis/results/v4-three-state-duration-20261005-v1'
Q_C=4.0
Q_ALPHA=0.75
RIDGE_ALPHAS=[5.0,20.0,80.0]


def fit_duration(frame,train,which,features,alpha):
    if which=='start':
        mask=train&(frame.y.to_numpy(int)==1)
    elif which=='sub':
        mask=train&(frame.y.to_numpy(int)==0)&(frame.minutes.to_numpy(float)>0)
    else:raise ValueError(which)
    model=make_pipeline(StandardScaler(),Ridge(alpha=alpha))
    model.fit(frame.loc[mask,features],frame.loc[mask,'minutes'])
    pred=np.clip(model.predict(frame[features]),0,90)
    stored={'features':features,'alpha':float(alpha),'coefficients':np.ravel(model[-1].coef_).tolist(),
            'intercept':float(np.ravel(model[-1].intercept_)[0]),
            'scaler_mean':model[0].mean_.tolist(),'scaler_scale':model[0].scale_.tolist(),
            'training_rows':int(mask.sum())}
    return pred,stored


def conditional_metrics(frame,mask,start_pred,sub_pred):
    y=frame.y.to_numpy(int);m=frame.minutes.to_numpy(float)
    s=mask&(y==1);q=mask&(y==0)&(m>0)
    def one(z,p):
        e=p[z]-m[z]
        return {'n':int(z.sum()),'mae':float(np.mean(np.abs(e))),
                'rmse':float(np.sqrt(np.mean(e**2))),'bias':float(np.mean(e))}
    return {'start':one(s,start_pred),'sub':one(q,sub_pred)}


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    protocol={
      'name':'v4 3-state v3 conditional-duration exploration',
      'fixed_start_probability':'v4',
      'fixed_substate':'v4-3S-v2 binary_sequence C=4 alpha=0.75',
      'development_train':'GW6-15','development_compare':'GW16-21 already reused for prior decisions',
      'final_train':'GW6-21','reused_diagnostic':'GW22-38',
      'duration_candidates':['frozen_v4','sequence_start','sequence_sub','sequence_both'],
      'ridge_alpha_grid':RIDGE_ALPHAS,
      'selection':'development xMins RMSE; prefer simpler/frozen model within 0.01 min',
      'warning':'exploratory sequential tuning; independent season/test required before promotion'
    }
    write_json(OUT/'protocol.json',protocol)

    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    # Explicit component features + workload + sequence. Avoid outcome/posthoc fields.
    X=component_inputs(frame)
    for c in WORKLOAD_FEATURES+SEQ_FEATURES:X[c]=frame[c].to_numpy(float)
    dur_features=list(X.columns)
    # Copy materialized X into frame with a prefix-free exact schema where absent.
    for c in dur_features:
        if c not in frame:frame[c]=X[c]

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev=frame.gw.between(16,21).to_numpy()
    devcut=pd.to_datetime(frame.loc[dev,'cutoff'],utc=True).min()
    tr=(frame.gw.between(6,15)&(known<devcut)).to_numpy()
    pdev,_=fit_v4_start(frame,tr)
    q0=np.clip(frame.p_cameo_given_bench.to_numpy(float),1e-6,1-1e-6)
    qhat,_=fit_q(frame,tr,BASE_Q_FEATURES+SEQ_FEATURES,Q_C)
    qdev=expit((1-Q_ALPHA)*logit(q0)+Q_ALPHA*logit(np.clip(qhat,1e-6,1-1e-6)))

    frozen_s=frame.start_minutes_mean.to_numpy(float)
    frozen_c=frame.cameo_minutes_mean.to_numpy(float)
    base_xm=pdev*frozen_s+(1-pdev)*qdev*frozen_c
    base=metrics(frame,dev,pdev,qdev,base_xm)

    rows=[];models={}
    duration_cache={}
    for a in RIDGE_ALPHAS:
        sp,sm=fit_duration(frame,tr,'start',dur_features,a)
        cp,cm=fit_duration(frame,tr,'sub',dur_features,a)
        duration_cache[a]=(sp,cp);models[f'alpha_{a:g}']={'start':sm,'sub':cm}
        for variant in ('sequence_start','sequence_sub','sequence_both'):
            s=sp if variant in ('sequence_start','sequence_both') else frozen_s
            c=cp if variant in ('sequence_sub','sequence_both') else frozen_c
            xm=pdev*s+(1-pdev)*qdev*c
            met=metrics(frame,dev,pdev,qdev,xm)
            rows.append({'variant':variant,'ridge_alpha':a,**met,
                         'delta_rmse':met['xmins_rmse']-base['xmins_rmse'],
                         'delta_mae':met['xmins_mae']-base['xmins_mae']})
    cand=pd.DataFrame(rows).sort_values(['xmins_rmse','xmins_mae','variant','ridge_alpha'])
    if len(cand) and cand.iloc[0].xmins_rmse<base['xmins_rmse']-0.01:
        best=cand.iloc[0];selected=str(best.variant);selA=float(best.ridge_alpha)
    else:selected='frozen_v4';selA=None
    cand.to_csv(OUT/'development_candidates.csv',index=False)
    selection={'fixed_v2_substate':base,'selected_duration':selected,'selected_ridge_alpha':selA}
    write_json(OUT/'selection.json',selection)
    write_json(OUT/'development_duration_models.json',models)
    write_json(OUT/'development_conditional_metrics.json',
               conditional_metrics(frame,dev,frozen_s,frozen_c))

    # Final train + reused diagnostic.
    test=frame.gw.between(22,38).to_numpy()
    cutoff=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
    finaltr=(frame.gw.between(6,21)&(known<cutoff)).to_numpy()
    pfinal,_=fit_v4_start(frame,finaltr)
    qhat_final,qmodel=fit_q(frame,finaltr,BASE_Q_FEATURES+SEQ_FEATURES,Q_C)
    qfinal=expit((1-Q_ALPHA)*logit(q0)+Q_ALPHA*logit(np.clip(qhat_final,1e-6,1-1e-6)))
    base_xm=pfinal*frozen_s+(1-pfinal)*qfinal*frozen_c
    base_test=metrics(frame,test,pfinal,qfinal,base_xm)

    if selected=='frozen_v4':
        sf=frozen_s;cf=frozen_c;final_models=None
    else:
        sp,sm=fit_duration(frame,finaltr,'start',dur_features,selA)
        cp,cm=fit_duration(frame,finaltr,'sub',dur_features,selA)
        sf=sp if selected in ('sequence_start','sequence_both') else frozen_s
        cf=cp if selected in ('sequence_sub','sequence_both') else frozen_c
        final_models={'start':sm,'sub':cm}
    xm=pfinal*sf+(1-pfinal)*qfinal*cf
    new_test=metrics(frame,test,pfinal,qfinal,xm)

    cond_base=conditional_metrics(frame,test,frozen_s,frozen_c)
    cond_new=conditional_metrics(frame,test,sf,cf)
    write_json(OUT/'reused_diagnostic_conditional_metrics.json',{'frozen_v4':cond_base,'selected':cond_new})

    state=np.where(frame.y.to_numpy(int)==1,2,np.where(frame.minutes.to_numpy(float)>0,1,0))
    groups=[
      ('all',test),
      ('sequence_changed',test&(frame.seq_changed_state_last.to_numpy()>0.5)),
      ('strong_uptrend',test&(frame.seq_trend_2_vs_prev3.to_numpy()>=20)),
      ('strong_downtrend',test&(frame.seq_trend_2_vs_prev3.to_numpy()<=-20)),
      ('POSTHOC_starter',test&(state==2)),
      ('POSTHOC_substitute',test&(state==1)),
      ('POSTHOC_zero',test&(state==0)),
    ]
    sr=[]
    for label,m in groups:
        if not m.any():continue
        sr.append({'slice':label,'arm':'v4_3S_v2_frozen_duration',**metrics(frame,m,pfinal,qfinal,base_xm)})
        sr.append({'slice':label,'arm':'v4_3S_v3_duration',**metrics(frame,m,pfinal,qfinal,xm)})
    pd.DataFrame(sr).to_csv(OUT/'diagnostic_slices.csv',index=False)

    result={
      'classification':'exploratory sequential development iteration; no independent confirmation',
      'development_selection':selection,
      'reused_diagnostic':{
        'v4_3S_v2':base_test,'v4_3S_v3':new_test,
        'delta_v3_minus_v2':{k:new_test[k]-base_test[k] for k in ['xmins_mae','xmins_rmse','xmins_bias']},
        'conditional_frozen':cond_base,'conditional_selected':cond_new,
      },
      'p_start_unchanged_v4':True,'substate_fixed_from_v2':True,'promoted':False
    }
    write_json(OUT/'result.json',result)
    write_json(OUT/'frozen_models.json',{'q_model':qmodel,'duration_models':final_models})
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',{
      'sources':[{'path':str(SOURCE.relative_to(ROOT)),'sha256':sha(SOURCE)},
                 {'path':'scripts/run_v4_three_state_duration_experiment.py','sha256':sha(Path(__file__))}],
      'outputs':[{'path':p.name,'sha256':sha(p)} for p in outs]})
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
