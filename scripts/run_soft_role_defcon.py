#!/usr/bin/env python3
"""Soft-role-conditioned DefCon residual experiment.

Question
--------
Does recent defensive performance interact with the player's *soft* tactical
role distribution in a useful way for DefCon, without forcing formations into
hard buckets?

Baseline is the already selected soft-role DefCon prior. We compare residual
models:
  shared: one common recent-performance effect
  soft: shared effects + interactions with overlapping q(role) tactical axes
  hard: shared effects + interactions with one primary axis (diagnostic only)

The soft axes overlap by design (e.g. RWB contributes to back and wingback),
so this does not assume every formation has rigid slots.

Development: GW16-21 leave-one-GW-out CV on conditional DefCon count deviance.
Reused diagnostic: GW22-38, applying the selected multiplicative residual on
top of the existing role-candidate mu_dc while leaving minutes/opponent factor
and every other event component unchanged.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.paired_joint import read_frozen_table,build_pair,run_pair
from fpl_v1_1_model.role_classifier import ROLES
from run_v4_performance_rating_experiment import SOURCE,add_features as add_perf_features
from run_v4rc_experiment import sha,write_json

ROLE=ROOT/'analysis/results/role-event-priors-20261005-v1'
PERF=ROOT/'analysis/results/v4-performance-rating-20261005-v1/performance_ledger.csv.gz'
FROZEN=ROOT/'analysis/results/deadline-joint-inputs-v1'
OUT=ROOT/'analysis/results/soft-role-defcon-20261005-v1'
KEYS=['fixture_uuid','player_uuid','team_id']
QCOLS=['q_'+r+'_slow' for r in ROLES]

AXES={
 'cb':['RCB','CB','LCB'],
 'fullback':['RB','LB'],
 'wingback':['RWB','LWB'],
 'dm':['RDM','DM','LDM'],
 'cm':['RCM','CM','LCM'],
 'attacking_mid':['CAM','RAM','LAM','RW','LW'],
 'forward':['SS','ST'],
}
BASE_FEATURES=['perf_last_def_actions','perf_last_minutes','perf_last_rating_proxy']
L2=[10.0,50.0,200.0]


def score(y,p):
    e=np.asarray(p)-np.asarray(y)
    return dict(mae=float(np.mean(np.abs(e))),rmse=float(np.sqrt(np.mean(e**2))),bias=float(np.mean(e)))


def poisson_deviance(y,mu):
    y=np.asarray(y,float);mu=np.maximum(np.asarray(mu,float),1e-12)
    t=mu-y;pos=y>0;t[pos]+=y[pos]*np.log(y[pos]/mu[pos])
    return float(2*np.mean(t))


def add_axes(frame):
    f=frame.copy()
    for axis,roles in AXES.items():
        f['axis_'+axis]=f[['q_'+r+'_slow' for r in roles]].fillna(0).sum(axis=1)
    return f


def design(frame,mode):
    X=frame[BASE_FEATURES].astype(float).copy()
    axes=['axis_'+a for a in AXES]
    if mode=='shared':return X
    if mode=='soft':
        for feat in BASE_FEATURES:
            for a in axes:
                X[f'{feat}__{a}']=frame[feat].to_numpy(float)*frame[a].to_numpy(float)
        return X
    if mode=='hard':
        A=frame[axes].to_numpy(float);primary=np.argmax(A,axis=1);known=A.max(axis=1)>0
        for feat in BASE_FEATURES:
            v=frame[feat].to_numpy(float)
            for j,a in enumerate(axes):
                X[f'{feat}__hard_{a}']=v*((primary==j)&known)
        return X
    raise ValueError(mode)


def fit_model(df,X,l2,train,base_mu):
    A=X.to_numpy(float);mu=A[train].mean(0);sd=A[train].std(0);sd[sd<1e-8]=1
    Z=(A-mu)/sd;y=df.defcon_count.to_numpy(float);off=np.log(np.maximum(base_mu,1e-9))
    Xt=Z[train];yt=y[train];ot=off[train]
    def fg(b):
        z=ot+Xt@b;pred=np.exp(np.clip(z,-20,20))
        loss=np.mean(pred-yt*z)+.5*l2*np.dot(b,b)/len(yt)
        grad=Xt.T@(pred-yt)/len(yt)+l2*b/len(yt)
        return float(loss),grad
    res=minimize(lambda b:fg(b),np.zeros(A.shape[1]),jac=True,method='L-BFGS-B',
                 bounds=[(-2,2)]*A.shape[1],options={'maxiter':2000,'maxls':100,'ftol':1e-10,'gtol':1e-7})
    if not res.success:
        res=minimize(lambda b:fg(b),np.zeros(A.shape[1]),jac=True,method='BFGS',
                     options={'maxiter':2000,'gtol':1e-6})
    if not res.success:raise RuntimeError(str(res.message))
    mult=np.exp(np.clip(Z@res.x,-3,3))
    return base_mu*mult,dict(columns=list(X.columns),l2=float(l2),coef=res.x.tolist(),
                             mean=mu.tolist(),scale=sd.tolist())


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    write_json(OUT/'protocol.json',dict(
      purpose='soft overlapping tactical-role conditioning for DefCon',
      axes=AXES,features=BASE_FEATURES,
      comparison=['shared','soft','hard diagnostic'],
      development='GW16-21 leave-one-GW-out CV on count deviance',
      joint='GW22-38 reused diagnostic; only mu_dc changes',
      promotion_allowed=False))

    feat=pd.read_csv(SOURCE).reset_index(drop=True)
    ledger=pd.read_csv(PERF);ledger.available_at=pd.to_datetime(ledger.available_at,utc=True)
    feat=add_perf_features(feat,ledger);feat=add_axes(feat)
    axes=['axis_'+a for a in AXES]
    cols=QCOLS+axes+BASE_FEATURES

    dev=read_frozen_table(ROLE,'development_prior_predictions')
    dev=dev[dev.tau==900].copy().reset_index(drop=True)
    dev=dev.merge(feat[KEYS+cols],on=KEYS,how='left',validate='one_to_one')
    dev[cols]=dev[cols].fillna(0.0)
    # Baseline selected role prior count mean. Opponent factor is intentionally
    # absent in this conditional prior test; the joint application keeps the
    # existing opponent factor unchanged.
    base_mu=np.maximum(dev.dc_role_prior90.to_numpy(float)*dev.minutes.to_numpy(float)/90,1e-9)
    base_dev=poisson_deviance(dev.defcon_count,base_mu)

    rows=[]
    for mode in ['shared','soft','hard']:
        X=design(dev,mode)
        for l2 in L2:
            cv=np.zeros(len(dev))
            for gw in sorted(dev.gw.unique()):
                tr=dev.gw.to_numpy()!=gw;te=~tr
                p,_=fit_model(dev,X,l2,tr,base_mu)
                cv[te]=p[te]
            loss=poisson_deviance(dev.defcon_count,cv)
            rows.append(dict(mode=mode,l2=l2,n_features=X.shape[1],cv_deviance=loss,
                             baseline_role_deviance=base_dev,delta=loss-base_dev))
    tab=pd.DataFrame(rows).sort_values(['cv_deviance','mode','l2']).reset_index(drop=True)
    tab.to_csv(OUT/'development_cv_metrics.csv',index=False)
    best=tab.iloc[0]
    if best.cv_deviance<base_dev-1e-10:
        mode=str(best['mode']);l2=float(best.l2)
        _,model=fit_model(dev,design(dev,mode),l2,np.ones(len(dev),bool),base_mu)
    else:
        mode='role_only';l2=None;model=None
    selection=dict(mode=mode,l2=l2,baseline_deviance=base_dev,
                   selected_cv_deviance=float(best.cv_deviance) if mode!='role_only' else base_dev)
    write_json(OUT/'selection.json',selection);write_json(OUT/'model.json',model)

    # Reused joint diagnostic. Start from role candidate and multiply its
    # already minutes/opponent-adjusted mu_dc by the selected residual.
    rolecand=read_frozen_table(ROLE,'candidate_inputs').sort_values(KEYS).reset_index(drop=True)
    need=axes+BASE_FEATURES
    rolecand=rolecand.merge(feat[KEYS+need],on=KEYS,how='left',validate='one_to_one')
    rolecand[need]=rolecand[need].fillna(0.0)
    cand=rolecand.copy()
    if model is not None:
        X=design(cand,mode).to_numpy(float)
        Z=(X-np.asarray(model['mean']))/np.asarray(model['scale'])
        mult=np.exp(np.clip(Z@np.asarray(model['coef']),-3,3))
        cand['mu_dc']=np.maximum(0,cand.mu_dc.to_numpy(float)*mult)
    cand[['fixture_uuid','player_uuid','team_id','gw','mu_dc']+need].to_csv(
        OUT/'diagnostic_dc_inputs.csv.gz',index=False,compression='gzip')

    truth=read_frozen_table(FROZEN,'targets')
    rec=[]
    for i,(fx,rg) in enumerate(rolecand.groupby('fixture_uuid',sort=True)):
        cg=cand[cand.fixture_uuid==fx]
        _,a=build_pair(rg);_,b=build_pair(cg)
        ra,rb=run_pair(a,b,n=240,seed=31092501+i)
        for r in rg.itertuples():
            rec.append(dict(fixture_uuid=fx,player_uuid=r.player_uuid,gw=r.gw,
                            role=ra[r.player_uuid]['xPts_nonbonus'],
                            defcon=rb[r.player_uuid]['xPts_nonbonus']))
    pred=pd.DataFrame(rec);sc=pred.merge(truth,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    y=sc.total_points-sc.bonus
    m0=score(y,sc.role);m1=score(y,sc.defcon)
    report=dict(classification='reused_diagnostic_not_independent_holdout',
      development_selection=selection,rows=len(sc),fixtures=int(sc.fixture_uuid.nunique()),
      draws_per_fixture=240,nonbonus={'role_baseline':m0,'soft_defcon_candidate':m1},
      delta={k:m1[k]-m0[k] for k in ['mae','rmse','bias']},
      soft_selected=(mode=='soft'),hard_selected=(mode=='hard'),promoted=False)
    write_json(OUT/'joint_metrics.json',report)
    pred.to_csv(OUT/'joint_predictions.csv.gz',index=False,compression='gzip')
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(
      sources=[dict(path=str(SOURCE.relative_to(ROOT)),sha256=sha(SOURCE)),
               dict(path=str(PERF.relative_to(ROOT)),sha256=sha(PERF)),
               dict(path='scripts/run_soft_role_defcon.py',sha256=sha(Path(__file__)))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
