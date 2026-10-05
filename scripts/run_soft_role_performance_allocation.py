#!/usr/bin/env python3
"""Soft-role-conditioned hierarchical goal/assist allocation.

Tests the user's concern that hard formation buckets are too rigid.

We compare:
  1) shared performance effects (existing hierarchical allocation idea)
  2) SOFT tactical-axis interactions derived from the full predeadline q(role)
     distribution; a player can be partly fullback, wingback, winger, CAM, etc.
  3) hard primary-axis interactions as a diagnostic comparator only.

Team goal and assist totals are conserved exactly. Only within-team allocation
changes. Development uses leave-one-GW-out CV on GW16-21. GW22-38 is reused
diagnostic only.
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
from run_v4_performance_rating_experiment import SOURCE, add_features as add_perf_features
from run_v4rc_experiment import sha, write_json

ROLE=ROOT/'analysis/results/role-event-priors-20261005-v1'
PERF=ROOT/'analysis/results/v4-performance-rating-20261005-v1/performance_ledger.csv.gz'
FROZEN=ROOT/'analysis/results/deadline-joint-inputs-v1'
OUT=ROOT/'analysis/results/soft-role-performance-allocation-20261005-v1'
KEYS=['fixture_uuid','player_uuid','team_id']
QCOLS=['q_'+r+'_slow' for r in ROLES]

# Continuous tactical axes. They deliberately overlap: a RWB can carry both
# "back" and "wide" signal; a RAM can carry "creative" and "wide/halfspace".
AXES={
 'cb':['RCB','CB','LCB'],
 'back':['RB','LB','RWB','LWB'],
 'wingback':['RWB','LWB'],
 'dm_cm':['RDM','DM','LDM','RCM','CM','LCM'],
 'creative':['CAM','RAM','LAM'],
 'wide_attack':['RW','LW','RAM','LAM'],
 'striker':['SS','ST'],
}

GOAL_BASE=['perf_last_xgi','perf_last_sot','perf_last_goal_assist']
ASSIST_BASE=['perf_last_xgi','perf_last_chances','perf_last_dribbles','perf_last_pass_acc']
L2=[10.0,50.0,200.0]


def score(y,p):
    e=np.asarray(p)-np.asarray(y)
    return dict(mae=float(np.mean(np.abs(e))),rmse=float(np.sqrt(np.mean(e**2))),bias=float(np.mean(e)))


def add_role_axes(frame):
    f=frame.copy()
    for axis,roles in AXES.items():
        cols=['q_'+r+'_slow' for r in roles]
        f['axis_'+axis]=f[cols].fillna(0).sum(axis=1)
    # UNKNOWN/zero role histories get no interaction; shared effects still work.
    return f


def build_design(frame,base_features,mode):
    """Return design DataFrame.

    shared: performance only.
    soft: shared + perf * continuous q-weighted tactical axes.
    hard: shared + perf * one-hot primary tactical axis (diagnostic comparator).
    """
    X=frame[base_features].astype(float).copy()
    if mode=='shared':
        return X
    axes=['axis_'+a for a in AXES]
    if mode=='soft':
        for feat in base_features:
            for a in axes:
                X[f'{feat}__{a}']=frame[feat].to_numpy(float)*frame[a].to_numpy(float)
        return X
    if mode=='hard':
        A=frame[axes].to_numpy(float)
        primary=np.argmax(A,axis=1)
        known=A.max(axis=1)>0
        for feat in base_features:
            v=frame[feat].to_numpy(float)
            for j,a in enumerate(axes):
                X[f'{feat}__hard_{a}']=v*((primary==j)&known)
        return X
    raise ValueError(mode)


def group_loss(y,share,group):
    y=np.asarray(y,float);share=np.clip(np.asarray(share,float),1e-12,1)
    total=0.;mass=0.
    for gid in np.unique(group):
        m=group==gid; yy=y[m]; Y=float(yy.sum())
        if Y<=1e-12: continue
        total+=float(-(yy*np.log(share[m])).sum());mass+=Y
    return total/max(mass,1e-12)


def fit_allocator(df,event,base_rate_col,X,l2,train):
    A=X.to_numpy(float)
    mu=A[train].mean(0);sd=A[train].std(0);sd[sd<1e-8]=1
    Z=(A-mu)/sd
    exposure=np.maximum(df.minutes.to_numpy(float)/90,0)
    base=np.maximum(df[base_rate_col].to_numpy(float)*exposure,1e-12)
    y=df[event].to_numpy(float)
    group=(df.fixture_uuid.astype(str)+'|'+df.team_id.astype(str)).to_numpy()
    train_groups=np.unique(group[train])

    def fg(beta):
        loss=0.;mass=0.;grad=np.zeros_like(beta)
        for gid in train_groups:
            idx=np.flatnonzero(train&(group==gid))
            yy=y[idx];Y=float(yy.sum())
            if Y<=1e-12:continue
            z=np.log(base[idx])+Z[idx]@beta;z-=z.max()
            w=np.exp(z);p=w/w.sum()
            loss+=float(-(yy*np.log(np.clip(p,1e-12,1))).sum());mass+=Y
            grad+=Z[idx].T@(p*Y-yy)
        scale=max(mass,1e-12)
        return float(loss/scale+.5*l2*np.dot(beta,beta)/scale),grad/scale+l2*beta/scale

    res=minimize(lambda b:fg(b),np.zeros(A.shape[1]),jac=True,method='L-BFGS-B',
                 bounds=[(-2.0,2.0)]*A.shape[1],
                 options={'maxiter':2000,'ftol':1e-10,'gtol':1e-7,'maxls':100})
    if not res.success:
        res=minimize(lambda b:fg(b),np.zeros(A.shape[1]),jac=True,method='BFGS',
                     options={'maxiter':2000,'gtol':1e-6})
    if not res.success:raise RuntimeError(str(res.message))

    raw=base*np.exp(np.clip(Z@res.x,-4,4))
    share=np.zeros(len(df))
    for gid in np.unique(group):
        idx=np.flatnonzero(group==gid);share[idx]=raw[idx]/raw[idx].sum()
    model=dict(columns=list(X.columns),l2=float(l2),coef=res.x.tolist(),mean=mu.tolist(),scale=sd.tolist())
    return share,model


def baseline_share(df,base_rate_col,exposure_col='minutes'):
    raw=np.maximum(df[base_rate_col].to_numpy(float)*df[exposure_col].to_numpy(float)/90,1e-12)
    group=(df.fixture_uuid.astype(str)+'|'+df.team_id.astype(str)).to_numpy()
    p=np.zeros(len(df))
    for gid in np.unique(group):
        idx=np.flatnonzero(group==gid);p[idx]=raw[idx]/raw[idx].sum()
    return p


def cv(df,event,base_rate,base_features):
    group=(df.fixture_uuid.astype(str)+'|'+df.team_id.astype(str)).to_numpy()
    base=baseline_share(df,base_rate)
    base_loss=group_loss(df[event],base,group)
    rows=[]
    for mode in ['shared','soft','hard']:
        X=build_design(df,base_features,mode)
        for l2 in L2:
            pred=np.zeros(len(df))
            for gw in sorted(df.gw.unique()):
                tr=df.gw.to_numpy()!=gw;te=~tr
                p,_=fit_allocator(df,event,base_rate,X,l2,tr);pred[te]=p[te]
            loss=group_loss(df[event],pred,group)
            rows.append(dict(mode=mode,l2=l2,cv_loss=loss,baseline_loss=base_loss,delta=loss-base_loss,
                             n_features=X.shape[1]))
    t=pd.DataFrame(rows).sort_values(['cv_loss','mode','l2']).reset_index(drop=True)
    best=t.iloc[0]
    if best.cv_loss>=base_loss-1e-10:return 'role_only',None,t
    return str(best['mode']),float(best.l2),t


def apply_model(df,base_rate,base_features,mode,model):
    exposure=np.maximum(df.control_xmins.to_numpy(float)/90,0)
    raw=np.maximum(df[base_rate].to_numpy(float)*exposure,1e-12)
    if model is not None:
        X=build_design(df,base_features,mode).to_numpy(float)
        Z=(X-np.asarray(model['mean']))/np.asarray(model['scale'])
        raw*=np.exp(np.clip(Z@np.asarray(model['coef']),-4,4))
    group=(df.fixture_uuid.astype(str)+'|'+df.team_id.astype(str)).to_numpy()
    p=np.zeros(len(df))
    for gid in np.unique(group):
        idx=np.flatnonzero(group==gid);p[idx]=raw[idx]/raw[idx].sum()
    return p


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    write_json(OUT/'protocol.json',dict(
      purpose='test soft q(role)-conditioned performance without hard formation buckets',
      axes=AXES,
      comparison=['shared','soft','hard diagnostic'],
      team_totals='exactly conserved',
      development='GW16-21 leave-one-GW-out CV',
      reused_diagnostic='GW22-38 only',
      promotion_allowed=False))

    feat=pd.read_csv(SOURCE).reset_index(drop=True)
    ledger=pd.read_csv(PERF);ledger.available_at=pd.to_datetime(ledger.available_at,utc=True)
    feat=add_perf_features(feat,ledger)
    feat=add_role_axes(feat)

    dev=read_frozen_table(ROLE,'development_prior_predictions')
    dev=dev[dev.tau==900].copy().reset_index(drop=True)
    extra=sorted(set(GOAL_BASE+ASSIST_BASE+QCOLS+['axis_'+a for a in AXES]))
    # axes currently only exist in feat; q included for provenance/diagnostics.
    dev=dev.merge(feat[KEYS+extra],on=KEYS,how='left',validate='one_to_one')
    dev[extra]=dev[extra].fillna(0.)

    selections={};tables=[];models={}
    for kind,event,base,features in [
      ('goal','xg','goal_role_prior90',GOAL_BASE),
      ('assist','xa','assist_role_prior90',ASSIST_BASE)]:
        mode,l2,t=cv(dev,event,base,features);t.insert(0,'component',kind);tables.append(t)
        selections[kind]=dict(mode=mode,l2=l2)
        if mode=='role_only':models[kind]=None
        else:
            X=build_design(dev,features,mode)
            _,models[kind]=fit_allocator(dev,event,base,X,l2,np.ones(len(dev),bool))
    pd.concat(tables,ignore_index=True).to_csv(OUT/'development_cv_metrics.csv',index=False)
    write_json(OUT/'selection.json',selections);write_json(OUT/'models.json',models)

    rolecand=read_frozen_table(ROLE,'candidate_inputs').sort_values(KEYS).reset_index(drop=True)
    extra2=sorted(set(GOAL_BASE+ASSIST_BASE+['axis_'+a for a in AXES]))
    rolecand=rolecand.merge(feat[KEYS+extra2],on=KEYS,how='left',validate='one_to_one')
    rolecand[extra2]=rolecand[extra2].fillna(0.)
    cand=rolecand.copy()

    gs=apply_model(cand,'goal_rate90',GOAL_BASE,selections['goal']['mode'],models['goal'])
    ass=apply_model(cand,'assist_rate90',ASSIST_BASE,selections['assist']['mode'],models['assist'])
    lam=np.where(cand.team_id==cand.home_team_id,cand.lambda_home_goals,cand.lambda_away_goals)
    cand['goal_mu']=lam*gs
    cand['assist_mu']=lam*cand.assist_probability_per_goal*ass

    # conservation
    audit=[]
    for (fx,team),g in cand.groupby(['fixture_uuid','team_id']):
        target=float(g.lambda_home_goals.iloc[0] if team==g.home_team_id.iloc[0] else g.lambda_away_goals.iloc[0])
        apg=float(g.assist_probability_per_goal.iloc[0])
        audit.append((fx,team,float(g.goal_mu.sum()),target,float(g.assist_mu.sum()),target*apg))
    aud=pd.DataFrame(audit,columns=['fixture_uuid','team_id','goal_total','goal_target','assist_total','assist_target'])
    assert np.max(np.abs(aud.goal_total-aud.goal_target))<1e-10
    assert np.max(np.abs(aud.assist_total-aud.assist_target))<1e-10
    aud.to_csv(OUT/'team_total_conservation.csv',index=False)

    # joint paired role baseline vs selected soft/shared candidate
    truth=read_frozen_table(FROZEN,'targets')
    rows=[]
    for i,(fx,rg) in enumerate(rolecand.groupby('fixture_uuid',sort=True)):
        cg=cand[cand.fixture_uuid==fx]
        _,a=build_pair(rg);_,b=build_pair(cg)
        ra,rb=run_pair(a,b,n=240,seed=30092501+i)
        for r in rg.itertuples():
            rows.append(dict(fixture_uuid=fx,player_uuid=r.player_uuid,gw=r.gw,
                             role=ra[r.player_uuid]['xPts_nonbonus'],
                             conditioned=rb[r.player_uuid]['xPts_nonbonus']))
    pred=pd.DataFrame(rows);sc=pred.merge(truth,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    y=sc.total_points-sc.bonus
    m0=score(y,sc.role);m1=score(y,sc.conditioned)
    report=dict(classification='reused_diagnostic_not_independent_holdout',
      development_selection=selections,rows=len(sc),fixtures=int(sc.fixture_uuid.nunique()),
      draws_per_fixture=240,nonbonus={'role_baseline':m0,'role_conditioned':m1},
      delta={k:m1[k]-m0[k] for k in ['mae','rmse','bias']},
      soft_role_selected=any(v['mode']=='soft' for v in selections.values()),
      hard_role_selected=any(v['mode']=='hard' for v in selections.values()),
      team_totals_preserved=True,promoted=False)
    write_json(OUT/'joint_metrics.json',report)
    pred.to_csv(OUT/'joint_predictions.csv.gz',index=False,compression='gzip')
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(
      sources=[dict(path=str(SOURCE.relative_to(ROOT)),sha256=sha(SOURCE)),
               dict(path=str(PERF.relative_to(ROOT)),sha256=sha(PERF)),
               dict(path='scripts/run_soft_role_performance_allocation.py',sha256=sha(Path(__file__)))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
