#!/usr/bin/env python3
"""Finish DefCon candidate by calibrating threshold probabilities.

Uses the already selected soft-role DefCon count candidate, then calibrates the
probability of crossing the official FPL threshold on GW16-21 only. Calibration
is converted back to an equivalent NB mean (same dispersion alpha), so the
existing simulator can consume a calibrated mu_dc without a special scoring
hack.

Candidates:
- none
- global Platt calibration
- broad-position Platt calibration (DEF/MID/FWD)
Selection: leave-one-GW-out threshold log loss, with count deviance as guardrail.
GW22-38 remains reused joint diagnostic only.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize,brentq
from scipy.special import expit,logit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.defcon import threshold,threshold_probability
from fpl_v1_1_model.paired_joint import read_frozen_table,build_pair,run_pair
from run_v4_performance_rating_experiment import SOURCE,add_features as add_perf_features
from run_soft_role_defcon import add_axes,design,fit_model,BASE_FEATURES,AXES,KEYS
from run_v4rc_experiment import write_json,sha

ROLE=ROOT/'analysis/results/role-event-priors-20261005-v1'
PERF=ROOT/'analysis/results/v4-performance-rating-20261005-v1/performance_ledger.csv.gz'
SOFT=ROOT/'analysis/results/soft-role-defcon-20261005-v1'
FROZEN=ROOT/'analysis/results/deadline-joint-inputs-v1'
OUT=ROOT/'analysis/results/defcon-threshold-finalist-20261005-v1'


def bce(y,p):
    p=np.clip(np.asarray(p,float),1e-9,1-1e-9);y=np.asarray(y,float)
    return float(-np.mean(y*np.log(p)+(1-y)*np.log1p(-p)))


def brier(y,p):
    return float(np.mean((np.asarray(p)-np.asarray(y))**2))


def fit_platt(p,y,pos,mode,train):
    z=logit(np.clip(p,1e-6,1-1e-6))
    if mode=='global':
        X=np.c_[np.ones(len(z)),z]
    elif mode=='position':
        cats=['DEF','MID','FWD']
        X=np.c_[z]+[(pos==c).astype(float) for c in cats]
    else: raise ValueError(mode)
    Xt=X[train];yt=y[train]
    def fg(b):
        q=expit(Xt@b)
        loss=-np.mean(yt*np.log(np.clip(q,1e-12,1))+(1-yt)*np.log(np.clip(1-q,1e-12,1)))+0.5*20*np.dot(b,b)/len(yt)
        grad=Xt.T@(q-yt)/len(yt)+20*b/len(yt)
        return float(loss),grad
    init=np.array([0.,1.]) if mode=='global' else np.array([1.,0.,0.,0.])
    res=minimize(lambda b:fg(b),init,jac=True,method='L-BFGS-B')
    if not res.success: raise RuntimeError(res.message)
    return expit(X@res.x),dict(mode=mode,coef=res.x.tolist())


def invert_p(target_p,pos,alpha):
    t=threshold(pos)
    if t is None:return 0.
    target=float(np.clip(target_p,1e-8,1-1e-8))
    f=lambda mu:threshold_probability(mu,pos,alpha)-target
    return float(brentq(f,1e-8,100.0,maxiter=100))


def score(y,p):
    e=np.asarray(p)-np.asarray(y)
    return dict(mae=float(np.mean(np.abs(e))),rmse=float(np.sqrt(np.mean(e**2))),bias=float(np.mean(e)))


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    write_json(OUT/'protocol.json',dict(
      development='GW16-21 leave-one-GW-out',
      target='official DefCon threshold event by FPL broad position',
      calibration_candidates=['none','global Platt','position Platt'],
      conversion='calibrated threshold probability inverted to equivalent NB mu with unchanged alpha',
      reused_diagnostic='GW22-38 joint only',promotion_allowed=False))

    soft_sel=json.loads((SOFT/'selection.json').read_text())
    soft_model=json.loads((SOFT/'model.json').read_text())

    feat=pd.read_csv(SOURCE).reset_index(drop=True)
    ledger=pd.read_csv(PERF);ledger.available_at=pd.to_datetime(ledger.available_at,utc=True)
    feat=add_axes(add_perf_features(feat,ledger))
    axes=['axis_'+a for a in AXES]

    dev=read_frozen_table(ROLE,'development_prior_predictions')
    dev=dev[dev.tau==900].copy().reset_index(drop=True)
    need=BASE_FEATURES+axes
    dev=dev.merge(feat[KEYS+['pos']+need],on=KEYS,how='left',validate='one_to_one');dev[need]=dev[need].fillna(0.)
    base_mu=np.maximum(dev.dc_role_prior90.to_numpy(float)*dev.minutes.to_numpy(float)/90,1e-9)
    X=design(dev,soft_sel['mode'])
    _,model=fit_model(dev,X,float(soft_sel['l2']),np.ones(len(dev),bool),base_mu)
    A=X.to_numpy(float);Z=(A-np.asarray(model['mean']))/np.asarray(model['scale'])
    soft_mu=base_mu*np.exp(np.clip(Z@np.asarray(model['coef']),-3,3))

    # alpha from FPL broad pos
    fit=json.loads((ROOT/'analysis/results/joint-component-recovery-v1/defcon_fit.json').read_text())
    alphas=fit['selected']['nb2_dispersion_alpha']
    pos=dev.pos.replace({'GKP':'GK'}).to_numpy()
    alpha=np.array([alphas.get(x,0.) for x in pos],float)
    y=np.array([1. if threshold(str(p)) and c>=threshold(str(p)) else 0. for p,c in zip(pos,dev.defcon_count)],float)
    p0=np.array([threshold_probability(m,str(p),a) for m,p,a in zip(soft_mu,pos,alpha)])

    rows=[dict(candidate='none',log_loss=bce(y,p0),brier=brier(y,p0))]
    oof={}
    for mode in ['global','position']:
        q=np.zeros(len(dev))
        for gw in sorted(dev.gw.unique()):
            tr=dev.gw.to_numpy()!=gw;te=~tr
            qq,_=fit_platt(p0,y,pos,mode,tr);q[te]=qq[te]
        oof[mode]=q
        rows.append(dict(candidate=mode,log_loss=bce(y,q),brier=brier(y,q)))
    tab=pd.DataFrame(rows).sort_values(['log_loss','brier']);tab.to_csv(OUT/'development_threshold_metrics.csv',index=False)
    selected=str(tab.iloc[0].candidate)
    if selected=='none':cal_model=None
    else:
        _,cal_model=fit_platt(p0,y,pos,selected,np.ones(len(dev),bool))
    write_json(OUT/'selection.json',dict(selected=selected,model=cal_model,
      baseline_event_rate=float(y.mean()),baseline_mean_p=float(p0.mean()),
      selected_oof_mean_p=float(oof[selected].mean()) if selected!='none' else float(p0.mean())))

    # Reused joint: reconstruct soft residual on current role candidate mu.
    rolecand=read_frozen_table(ROLE,'candidate_inputs').sort_values(KEYS).reset_index(drop=True)
    rolecand=rolecand.merge(feat[KEYS+need],on=KEYS,how='left',validate='one_to_one');rolecand[need]=rolecand[need].fillna(0.)
    cand=rolecand.copy()
    Xj=design(cand,soft_sel['mode']).to_numpy(float)
    Zj=(Xj-np.asarray(model['mean']))/np.asarray(model['scale'])
    mu_soft=np.maximum(1e-9,cand.mu_dc.to_numpy(float)*np.exp(np.clip(Zj@np.asarray(model['coef']),-3,3)))
    posj=cand.pos.replace({'GKP':'GK'}).to_numpy()
    alphaj=cand.dc_alpha.to_numpy(float)
    pj=np.array([threshold_probability(m,str(p),a) for m,p,a in zip(mu_soft,posj,alphaj)])
    if cal_model is None:
        pcal=pj
    else:
        z=logit(np.clip(pj,1e-6,1-1e-6))
        if selected=='global':
            M=np.c_[np.ones(len(z)),z]
        else:
            M=np.c_[z]+[(posj==c).astype(float) for c in ['DEF','MID','FWD']]
        pcal=expit(M@np.asarray(cal_model['coef']))
    mu_cal=np.array([invert_p(p,str(po),a) if str(po) in ('DEF','MID','FWD') else 0. for p,po,a in zip(pcal,posj,alphaj)])
    cand['mu_dc']=mu_cal

    truth=read_frozen_table(FROZEN,'targets')
    rec=[]
    for i,(fx,rg) in enumerate(rolecand.groupby('fixture_uuid',sort=True)):
        cg=cand[cand.fixture_uuid==fx]
        _,a=build_pair(rg);_,b=build_pair(cg)
        ra,rb=run_pair(a,b,n=320,seed=32092501+i)
        for r in rg.itertuples():
            rec.append(dict(fixture_uuid=fx,player_uuid=r.player_uuid,gw=r.gw,
                            role=ra[r.player_uuid]['xPts_nonbonus'],final_dc=rb[r.player_uuid]['xPts_nonbonus']))
    pred=pd.DataFrame(rec);sc=pred.merge(truth,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    yy=sc.total_points-sc.bonus;m0=score(yy,sc.role);m1=score(yy,sc.final_dc)
    report=dict(classification='reused_diagnostic_not_independent_holdout',
      selected_calibration=selected,development_metrics=rows,rows=len(sc),fixtures=int(sc.fixture_uuid.nunique()),
      draws_per_fixture=320,nonbonus={'role_baseline':m0,'final_dc':m1},
      delta={k:m1[k]-m0[k] for k in ['mae','rmse','bias']},promoted=False)
    write_json(OUT/'joint_metrics.json',report)
    pred.to_csv(OUT/'joint_predictions.csv.gz',index=False,compression='gzip')
    pd.DataFrame({'fixture_uuid':cand.fixture_uuid,'player_uuid':cand.player_uuid,'pos':posj,
                  'mu_soft':mu_soft,'p_soft':pj,'p_cal':pcal,'mu_cal':mu_cal}).to_csv(
                      OUT/'calibrated_dc.csv.gz',index=False,compression='gzip')
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(
      sources=[dict(path='scripts/run_defcon_threshold_finalist.py',sha256=sha(Path(__file__)))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
