#!/usr/bin/env python3
"""Exploratory goal/assist test: soft roles + recent match performance.

Purpose
-------
Test whether recent performance/rating information adds signal on top of the
already development-selected soft-role priors for goal and assist rates.

Because the original role-prior development artifact only covers GW16-21,
performance coefficients are assessed with leave-one-GW-out cross-validation
inside GW16-21. No tuning uses GW22-38. After candidate family selection, the
coefficient is refit on all GW16-21 and applied to the already frozen
role-candidate rates for the reused GW22-38 joint diagnostic.

This is exploratory and cannot be promoted without an independent period.
"""
from __future__ import annotations
import json, hashlib
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.paired_joint import read_frozen_table,build_pair,run_pair
from run_v4_performance_rating_experiment import SOURCE, add_features as add_perf_features
from run_v4rc_experiment import sha, write_json

ROLE=ROOT/'analysis/results/role-event-priors-20261005-v1'
PERF=ROOT/'analysis/results/v4-performance-rating-20261005-v1/performance_ledger.csv.gz'
FROZEN=ROOT/'analysis/results/deadline-joint-inputs-v1'
OUT=ROOT/'analysis/results/role-performance-goal-assist-20261005-v1'

FAMILIES={
  'rating':['perf_last_rating_proxy'],
  'support':['perf_last_minutes','perf_last_sot','perf_last_chances','perf_last_dribbles',
             'perf_last_pass_acc','perf_last_dispossessed','perf_last_def_actions'],
  'rating_support':['perf_last_rating_proxy','perf_last_minutes','perf_last_sot','perf_last_chances',
                    'perf_last_dribbles','perf_last_pass_acc','perf_last_dispossessed','perf_last_def_actions'],
}
L2=[0.5,2.0,10.0]


def poisson_deviance(y,mu):
    y=np.asarray(y,float);mu=np.maximum(np.asarray(mu,float),1e-12)
    term=mu-y
    pos=y>0
    term[pos]+=y[pos]*np.log(y[pos]/mu[pos])
    return float(2*np.mean(term))


def fit_offset(df,event,prior_col,features,l2,train):
    X=df[features].to_numpy(float)
    mu=X[train].mean(0);sd=X[train].std(0);sd[sd<1e-8]=1
    Z=(X-mu)/sd
    exposure=np.maximum(df.minutes.to_numpy(float)/90,1e-9)
    base=np.maximum(df[prior_col].to_numpy(float)*exposure,1e-9)
    y=df[event].to_numpy(float)
    Xt=Z[train];yt=y[train];off=np.log(base[train])
    def fg(b):
        z=off+Xt@b
        pred=np.exp(np.clip(z,-20,20))
        loss=np.mean(pred-yt*z)+0.5*l2*np.dot(b,b)/len(yt)
        grad=Xt.T@(pred-yt)/len(yt)+l2*b/len(yt)
        return float(loss),grad
    res=minimize(lambda b:fg(b),np.zeros(len(features)),jac=True,method='L-BFGS-B')
    if not res.success: raise RuntimeError(res.message)
    pred=base*np.exp(np.clip(Z@res.x,-4,4))
    rate90=pred/exposure
    return pred,rate90,dict(features=features,l2=float(l2),coef=res.x.tolist(),mean=mu.tolist(),scale=sd.tolist())


def cv_select(df,kind,event,prior):
    rows=[]
    gws=sorted(df.gw.unique())
    base_dev=poisson_deviance(df[event],df[prior]*df.minutes/90)
    for fam,features in FAMILIES.items():
        for l2 in L2:
            preds=np.zeros(len(df)); rates=np.zeros(len(df))
            for gw in gws:
                train=(df.gw.to_numpy()!=gw)
                test=(df.gw.to_numpy()==gw)
                p,r,_=fit_offset(df,event,prior,features,l2,train)
                preds[test]=p[test];rates[test]=r[test]
            dev=poisson_deviance(df[event],preds)
            rows.append(dict(component=kind,candidate=fam,l2=l2,rows=len(df),
                             cv_deviance=dev,baseline_role_deviance=base_dev,
                             delta_deviance=dev-base_dev))
    t=pd.DataFrame(rows).sort_values(['cv_deviance','candidate','l2'])
    best=t.iloc[0]
    if best.cv_deviance>=base_dev-1e-10:
        return 'role_only',None,t
    return str(best.candidate),float(best.l2),t


def score(y,p):
    e=np.asarray(p)-np.asarray(y)
    return dict(mae=float(np.mean(np.abs(e))),rmse=float(np.sqrt(np.mean(e**2))),bias=float(np.mean(e)))


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)

    protocol=dict(
      question='Do recent match-performance features add goal/assist signal beyond soft roles?',
      development='GW16-21 leave-one-GW-out cross-validation only',
      reused_diagnostic='GW22-38 paired joint simulation after development selection',
      baseline='existing selected 900-minute soft-role prior',
      families=FAMILIES,l2=L2,
      isolation='current v4 minutes and all non-goal/assist components unchanged in joint diagnostic',
      promotion_allowed=False)
    write_json(OUT/'protocol.json',protocol)

    dev=read_frozen_table(ROLE,'development_prior_predictions')
    # One row per player-fixture repeated for 3 tau values: use selected tau=900.
    dev=dev[dev.tau==900].copy().reset_index(drop=True)
    feature_frame=pd.read_csv(SOURCE).reset_index(drop=True)
    ledger=pd.read_csv(PERF)
    ledger['available_at']=pd.to_datetime(ledger.available_at,utc=True)
    feature_frame=add_perf_features(feature_frame,ledger)
    perfcols=sorted(set(sum(FAMILIES.values(),[])))
    keys=['fixture_uuid','player_uuid','team_id']
    dev=dev.merge(feature_frame[keys+perfcols],on=keys,how='left',validate='one_to_one')
    dev[perfcols]=dev[perfcols].fillna(0.0)

    selections={};tables=[]
    for kind,event,prior in [('goal','xg','goal_role_prior90'),('assist','xa','assist_role_prior90')]:
        sel,l2,t=cv_select(dev,kind,event,prior);selections[kind]=dict(candidate=sel,l2=l2)
        tables.append(t)
    pd.concat(tables,ignore_index=True).to_csv(OUT/'development_cv_metrics.csv',index=False)
    write_json(OUT/'selection.json',selections)

    # Fit finalists on all dev rows.
    fitted={}
    for kind,event,prior in [('goal','xg','goal_role_prior90'),('assist','xa','assist_role_prior90')]:
        sel=selections[kind]['candidate']
        if sel=='role_only': fitted[kind]=None;continue
        p,r,m=fit_offset(dev,event,prior,FAMILIES[sel],selections[kind]['l2'],np.ones(len(dev),dtype=bool))
        fitted[kind]=m
    write_json(OUT/'fitted_models.json',fitted)

    # Reused joint diagnostic: start from existing role candidate; apply the
    # selected performance multiplier to its already-shrunk player rate90.
    baseline=read_frozen_table(FROZEN,'inputs').sort_values(keys).reset_index(drop=True)
    rolecand=read_frozen_table(ROLE,'candidate_inputs').sort_values(keys).reset_index(drop=True)
    assert baseline[keys].equals(rolecand[keys])
    rolecand=rolecand.merge(feature_frame[keys+perfcols],on=keys,how='left',validate='one_to_one')
    rolecand[perfcols]=rolecand[perfcols].fillna(0.0)

    candidate=rolecand.copy()
    for kind in ['goal','assist']:
        model=fitted[kind]
        if model is None:continue
        X=candidate[model['features']].to_numpy(float)
        Z=(X-np.asarray(model['mean']))/np.asarray(model['scale'])
        mult=np.exp(np.clip(Z@np.asarray(model['coef']),-2,2))
        candidate[kind+'_rate90']=np.maximum(0,candidate[kind+'_rate90'].to_numpy(float)*mult)

    lambdas=np.where(candidate.team_id==candidate.home_team_id,candidate.lambda_home_goals,candidate.lambda_away_goals)
    for kind in ['goal','assist']:
        prop=candidate.control_xmins/90*candidate[kind+'_rate90']
        total=prop.groupby([candidate.fixture_uuid,candidate.team_id]).transform('sum')
        candidate[kind+'_mu']=lambdas*prop/total*(candidate.assist_probability_per_goal if kind=='assist' else 1)

    # Save deterministic rate diagnostics before simulation.
    rate_summary=[]
    for kind in ['goal','assist']:
        rate_summary.append(dict(component=kind,
            mean_current_rate=float(baseline[kind+'_rate90'].mean()),
            mean_role_rate=float(rolecand[kind+'_rate90'].mean()),
            mean_role_perf_rate=float(candidate[kind+'_rate90'].mean())))
    pd.DataFrame(rate_summary).to_csv(OUT/'rate_summary.csv',index=False)

    # Paired simulation: compare current v4, existing role candidate, and new role+performance.
    truth=read_frozen_table(FROZEN,'targets')
    records=[]
    for i,(fixture,g) in enumerate(baseline.groupby('fixture_uuid',sort=True)):
        rg=rolecand[rolecand.fixture_uuid==fixture]
        cg=candidate[candidate.fixture_uuid==fixture]
        _,control=build_pair(g);_,role=build_pair(rg);_,perf=build_pair(cg)
        cs,rs=run_pair(control,role,n=120,seed=27092501+i)
        _,ps=run_pair(role,perf,n=120,seed=28092501+i)
        for r in g.itertuples():
            records.append(dict(fixture_uuid=fixture,player_uuid=r.player_uuid,gw=r.gw,
              current=cs[r.player_uuid]['xPts_nonbonus'],
              role=rs[r.player_uuid]['xPts_nonbonus'],
              role_performance=ps[r.player_uuid]['xPts_nonbonus']))
    pred=pd.DataFrame(records)
    scored=pred.merge(truth,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    y=scored.total_points-scored.bonus
    report=dict(rows=len(scored),fixtures=int(scored.fixture_uuid.nunique()),draws_per_fixture=120,
      development_selection=selections,
      nonbonus={arm:score(y,scored[arm]) for arm in ['current','role','role_performance']},
      classification='reused_diagnostic_not_independent_holdout',promoted=False)
    write_json(OUT/'joint_metrics.json',report)
    pred.to_csv(OUT/'joint_predictions.csv.gz',index=False,compression='gzip')

    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(
      sources=[dict(path=str(SOURCE.relative_to(ROOT)),sha256=sha(SOURCE)),
               dict(path=str(PERF.relative_to(ROOT)),sha256=sha(PERF)),
               dict(path='scripts/run_role_performance_goal_assist.py',sha256=sha(Path(__file__)))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
