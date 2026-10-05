#!/usr/bin/env python3
"""Hierarchical goal/assist allocation: team total fixed, player shares learned.

The model keeps the existing team goal/assist totals unchanged and only learns
how to distribute that mass among players. Existing soft-role + individual
history rates are the baseline allocation weights. Recent performance features
modify relative player weights inside each team-fixture:

    w_i = base_rate90_i * exposure_i * exp(beta' x_i)
    share_i = w_i / sum_j w_j
    mu_i = team_total * share_i

Thus performance can move probability between teammates but cannot inflate or
deflate the team's expected total goals/assists.

Development uses leave-one-GW-out CV on GW16-21 and a conditional allocation
loss. GW22-38 is a reused diagnostic only. No production promotion.
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

from fpl_v1_1_model.paired_joint import read_frozen_table, build_pair, run_pair
from run_v4_performance_rating_experiment import SOURCE, add_features as add_perf_features
from run_v4rc_experiment import sha, write_json

ROLE=ROOT/'analysis/results/role-event-priors-20261005-v1'
PERF=ROOT/'analysis/results/v4-performance-rating-20261005-v1/performance_ledger.csv.gz'
FROZEN=ROOT/'analysis/results/deadline-joint-inputs-v1'
OUT=ROOT/'analysis/results/hierarchical-goal-assist-allocation-20261005-v1'

GOAL_FAMILIES={
  'rating':['perf_last_rating_proxy'],
  'finishing':['perf_last_xgi','perf_last_sot','perf_last_goal_assist'],
  'rating_finishing':['perf_last_rating_proxy','perf_last_xgi','perf_last_sot',
                      'perf_last_goal_assist','perf_last_dribbles'],
}
ASSIST_FAMILIES={
  'rating':['perf_last_rating_proxy'],
  'creation':['perf_last_xgi','perf_last_chances','perf_last_dribbles',
              'perf_last_pass_acc'],
  'rating_creation':['perf_last_rating_proxy','perf_last_xgi','perf_last_chances',
                     'perf_last_dribbles','perf_last_pass_acc'],
}
L2=[0.5,2.0,10.0,50.0]
KEYS=['fixture_uuid','player_uuid','team_id']


def score(y,p):
    e=np.asarray(p)-np.asarray(y)
    return dict(mae=float(np.mean(np.abs(e))),rmse=float(np.sqrt(np.mean(e**2))),bias=float(np.mean(e)))


def group_loss(y,share,group_ids):
    """Conditional cross-entropy using continuous event mass (xG/xA)."""
    y=np.asarray(y,float);share=np.clip(np.asarray(share,float),1e-12,1)
    total=0.0;mass=0.0
    for gid in np.unique(group_ids):
        m=(group_ids==gid)
        ym=y[m]
        s=float(ym.sum())
        if s<=1e-12: continue
        total += float(-(ym*np.log(share[m])).sum())
        mass += s
    return total/max(mass,1e-12)


def fit_allocator(df,event,base_rate_col,features,l2,train):
    X=df[features].to_numpy(float)
    mu=X[train].mean(0);sd=X[train].std(0);sd[sd<1e-8]=1
    Z=(X-mu)/sd
    exposure=np.maximum(df.minutes.to_numpy(float)/90.0,0.0)
    base=np.maximum(df[base_rate_col].to_numpy(float)*exposure,1e-12)
    y=df[event].to_numpy(float)
    group=(df.fixture_uuid.astype(str)+'|'+df.team_id.astype(str)).to_numpy()

    train_idx=np.flatnonzero(train)
    train_groups=np.unique(group[train_idx])

    def objective(beta):
        total=0.0;mass=0.0
        grad=np.zeros_like(beta)
        for gid in train_groups:
            idx=np.flatnonzero(train & (group==gid))
            if len(idx)==0: continue
            yy=y[idx];Y=float(yy.sum())
            if Y<=1e-12: continue
            z=np.log(base[idx])+Z[idx]@beta
            z-=z.max()
            ww=np.exp(z);pp=ww/ww.sum()
            total += float(-(yy*np.log(np.clip(pp,1e-12,1))).sum())
            mass += Y
            grad += Z[idx].T @ (pp*Y-yy)
        loss=total/max(mass,1e-12)+0.5*l2*np.dot(beta,beta)/max(mass,1.0)
        grad=grad/max(mass,1e-12)+l2*beta/max(mass,1.0)
        return float(loss),grad

    res=minimize(lambda b:objective(b),np.zeros(len(features)),jac=True,method='L-BFGS-B',
                 bounds=[(-2.5,2.5)]*len(features),
                 options={'maxiter':2000,'ftol':1e-10,'gtol':1e-7,'maxls':100})
    if not res.success:
        # Numerical line-search failures can occur on very sparse assist mass.
        # The objective is smooth and convex enough for an unconstrained BFGS fallback.
        res=minimize(lambda b:objective(b),np.zeros(len(features)),jac=True,method='BFGS',
                     options={'maxiter':2000,'gtol':1e-6})
    if not res.success: raise RuntimeError(str(res.message))

    corr=np.exp(np.clip(Z@res.x,-4,4))
    raw=base*corr
    share=np.zeros(len(df),float)
    for gid in np.unique(group):
        idx=np.flatnonzero(group==gid)
        s=float(raw[idx].sum())
        if s<=0:
            share[idx]=1/len(idx)
        else:
            share[idx]=raw[idx]/s
    model=dict(features=features,l2=float(l2),coef=res.x.tolist(),mean=mu.tolist(),scale=sd.tolist())
    return share,model


def cv_select(df,event,base_col,families):
    rows=[];gws=sorted(int(x) for x in df.gw.unique())
    exposure=np.maximum(df.minutes.to_numpy(float)/90.0,0)
    base_raw=np.maximum(df[base_col].to_numpy(float)*exposure,1e-12)
    group=(df.fixture_uuid.astype(str)+'|'+df.team_id.astype(str)).to_numpy()
    base_share=np.zeros(len(df))
    for gid in np.unique(group):
        idx=np.flatnonzero(group==gid);base_share[idx]=base_raw[idx]/base_raw[idx].sum()
    base_loss=group_loss(df[event].to_numpy(float),base_share,group)

    for fam,features in families.items():
        for l2 in L2:
            cv=np.zeros(len(df))
            for gw in gws:
                train=(df.gw.to_numpy()!=gw)
                test=(df.gw.to_numpy()==gw)
                share,_=fit_allocator(df,event,base_col,features,l2,train)
                cv[test]=share[test]
            loss=group_loss(df[event].to_numpy(float),cv,group)
            rows.append(dict(candidate=fam,l2=l2,cv_loss=loss,baseline_loss=base_loss,delta=loss-base_loss))
    t=pd.DataFrame(rows).sort_values(['cv_loss','candidate','l2']).reset_index(drop=True)
    best=t.iloc[0]
    if float(best.cv_loss)>=base_loss-1e-10:
        return 'role_only',None,t
    return str(best.candidate),float(best.l2),t


def apply_model(df,base_rate_col,exposure_col,model):
    if model is None:
        raw=np.maximum(df[base_rate_col].to_numpy(float)*df[exposure_col].to_numpy(float)/90.0,1e-12)
    else:
        X=df[model['features']].to_numpy(float)
        Z=(X-np.asarray(model['mean']))/np.asarray(model['scale'])
        corr=np.exp(np.clip(Z@np.asarray(model['coef']),-4,4))
        raw=np.maximum(df[base_rate_col].to_numpy(float)*df[exposure_col].to_numpy(float)/90.0*corr,1e-12)
    group=(df.fixture_uuid.astype(str)+'|'+df.team_id.astype(str)).to_numpy()
    share=np.zeros(len(df))
    for gid in np.unique(group):
        idx=np.flatnonzero(group==gid);share[idx]=raw[idx]/raw[idx].sum()
    return share


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    OUT.mkdir(parents=True)

    protocol=dict(
      model='team-total-preserving hierarchical player allocation',
      baseline='existing soft-role + individual-history player rates',
      formula='share_i proportional to base_rate90_i * exposure_i * exp(beta*x_i)',
      team_totals='exactly preserved for goals and assists',
      development='GW16-21 leave-one-GW-out CV; conditional allocation loss',
      evaluation='GW22-38 reused joint diagnostic only',
      goal_families=GOAL_FAMILIES,assist_families=ASSIST_FAMILIES,l2=L2,
      promotion_allowed=False)
    write_json(OUT/'protocol.json',protocol)

    dev=read_frozen_table(ROLE,'development_prior_predictions')
    dev=dev[dev.tau==900].copy().reset_index(drop=True)

    features=pd.read_csv(SOURCE).reset_index(drop=True)
    ledger=pd.read_csv(PERF);ledger['available_at']=pd.to_datetime(ledger.available_at,utc=True)
    features=add_perf_features(features,ledger)

    perfcols=sorted(set(sum(GOAL_FAMILIES.values(),[])+sum(ASSIST_FAMILIES.values(),[])))
    dev=dev.merge(features[KEYS+perfcols],on=KEYS,how='left',validate='one_to_one')
    dev[perfcols]=dev[perfcols].fillna(0.0)

    gsel,gl2,gtab=cv_select(dev,'xg','goal_role_prior90',GOAL_FAMILIES)
    asel,al2,atab=cv_select(dev,'xa','assist_role_prior90',ASSIST_FAMILIES)
    gtab.insert(0,'component','goal');atab.insert(0,'component','assist')
    pd.concat([gtab,atab],ignore_index=True).to_csv(OUT/'development_cv_metrics.csv',index=False)

    models={}
    if gsel!='role_only':
        _,models_goal=fit_allocator(dev,'xg','goal_role_prior90',GOAL_FAMILIES[gsel],gl2,np.ones(len(dev),bool))
    else: models_goal=None
    if asel!='role_only':
        _,models_assist=fit_allocator(dev,'xa','assist_role_prior90',ASSIST_FAMILIES[asel],al2,np.ones(len(dev),bool))
    else: models_assist=None
    models={'goal':models_goal,'assist':models_assist}
    selection={'goal':{'candidate':gsel,'l2':gl2},'assist':{'candidate':asel,'l2':al2}}
    write_json(OUT/'selection.json',selection);write_json(OUT/'models.json',models)

    # Reused joint diagnostic. Start from the already role-adjusted candidate.
    rolecand=read_frozen_table(ROLE,'candidate_inputs').sort_values(KEYS).reset_index(drop=True)
    base=read_frozen_table(FROZEN,'inputs').sort_values(KEYS).reset_index(drop=True)
    rolecand=rolecand.merge(features[KEYS+perfcols],on=KEYS,how='left',validate='one_to_one')
    rolecand[perfcols]=rolecand[perfcols].fillna(0.0)
    candidate=rolecand.copy()

    goal_share=apply_model(candidate,'goal_rate90','control_xmins',models_goal)
    assist_share=apply_model(candidate,'assist_rate90','control_xmins',models_assist)
    team_lambda=np.where(candidate.team_id==candidate.home_team_id,candidate.lambda_home_goals,candidate.lambda_away_goals)
    candidate['goal_mu']=team_lambda*goal_share
    candidate['assist_mu']=team_lambda*candidate.assist_probability_per_goal*assist_share

    # Verify conservation exactly by team-fixture.
    audit=[]
    for (fixture,team),g in candidate.groupby(['fixture_uuid','team_id']):
        lam=float(g.lambda_home_goals.iloc[0] if team==g.home_team_id.iloc[0] else g.lambda_away_goals.iloc[0])
        apg=float(g.assist_probability_per_goal.iloc[0])
        audit.append(dict(fixture_uuid=fixture,team_id=team,
                          goal_total=float(g.goal_mu.sum()),goal_target=lam,
                          assist_total=float(g.assist_mu.sum()),assist_target=lam*apg))
    aud=pd.DataFrame(audit)
    assert np.max(np.abs(aud.goal_total-aud.goal_target))<1e-10
    assert np.max(np.abs(aud.assist_total-aud.assist_target))<1e-10
    aud.to_csv(OUT/'team_total_conservation.csv',index=False)

    # Save selected weight diagnostics.
    diag=candidate[KEYS+['gw','player','pos','expected_role','goal_rate90','assist_rate90','control_xmins']].copy()
    diag['goal_share']=goal_share;diag['assist_share']=assist_share
    diag.to_csv(OUT/'allocation_weights.csv.gz',index=False,compression='gzip')

    # Pair existing role allocation vs hierarchical allocation with common RNG.
    truth=read_frozen_table(FROZEN,'targets')
    rec=[]
    for i,(fixture,rg) in enumerate(rolecand.groupby('fixture_uuid',sort=True)):
        cg=candidate[candidate.fixture_uuid==fixture]
        _,control=build_pair(rg);_,treat=build_pair(cg)
        rs,ts=run_pair(control,treat,n=240,seed=29092501+i)
        for r in rg.itertuples():
            rec.append(dict(fixture_uuid=fixture,player_uuid=r.player_uuid,gw=r.gw,
                            role=rs[r.player_uuid]['xPts_nonbonus'],
                            hierarchical=ts[r.player_uuid]['xPts_nonbonus']))
        if (i+1)%24==0: print('fixtures',i+1,flush=True)
    pred=pd.DataFrame(rec)
    scored=pred.merge(truth,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    y=scored.total_points-scored.bonus
    report=dict(
      classification='reused_diagnostic_not_independent_holdout',
      rows=len(scored),fixtures=int(scored.fixture_uuid.nunique()),draws_per_fixture=240,
      development_selection=selection,
      nonbonus={'role_baseline':score(y,scored.role),'hierarchical':score(y,scored.hierarchical)},
      delta_hierarchical_minus_role={k:score(y,scored.hierarchical)[k]-score(y,scored.role)[k] for k in ['mae','rmse','bias']},
      team_goal_totals_preserved=True,team_assist_totals_preserved=True,promoted=False)
    write_json(OUT/'joint_metrics.json',report)
    pred.to_csv(OUT/'joint_predictions.csv.gz',index=False,compression='gzip')

    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(
      sources=[dict(path=str(SOURCE.relative_to(ROOT)),sha256=sha(SOURCE)),
               dict(path=str(PERF.relative_to(ROOT)),sha256=sha(PERF)),
               dict(path='scripts/run_hierarchical_goal_assist_allocation.py',sha256=sha(Path(__file__)))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
