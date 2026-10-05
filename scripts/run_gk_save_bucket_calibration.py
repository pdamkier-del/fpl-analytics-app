#!/usr/bin/env python3
"""Goalkeeper threshold-aware save distribution experiment.

Uses the frozen joint cohort and actual historical GK saves from core.sqlite3.
The existing lambda_saves remains the opportunity baseline. We only reweight the
Poisson count distribution across FPL save-point buckets:
  0-2, 3-5, 6-8, 9-11, 12+ saves.

This directly addresses the observed underprediction of P(>=3 saves) without
forcing a global lambda multiplier that would also disturb the already well
calibrated >=6 bucket.

Development selection: GW22-27 leave-one-GW-out within the already reused cohort.
Diagnostic: GW28-38. This is not independent validation.

The joint comparison is marginal on top of the saved DefCon finalist.
"""
from __future__ import annotations
import json,sys
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.paired_joint import read_frozen_table,build_pair,run_pair
from run_v4rc_experiment import write_json,sha

FROZEN=ROOT/'analysis/results/deadline-joint-inputs-v1'
ROLE=ROOT/'analysis/results/role-event-priors-20261005-v1'
DC=ROOT/'analysis/results/defcon-threshold-finalist-20261005-v1/calibrated_dc.csv.gz'
OUT=ROOT/'analysis/results/gk-save-bucket-calibration-20261005-v1'
L2=[1.0,10.0,50.0,200.0]


def bucket_index(s):
    return min(int(s)//3,4)


def base_bucket_probs(lam):
    # exact Poisson masses for save-point buckets
    cuts=[(0,2),(3,5),(6,8),(9,11),(12,80)]
    out=[]
    for lo,hi in cuts:
        if lo==0: p=poisson.cdf(hi,lam)
        elif hi>=80: p=poisson.sf(lo-1,lam)
        else: p=poisson.cdf(hi,lam)-poisson.cdf(lo-1,lam)
        out.append(max(float(p),1e-12))
    a=np.asarray(out,float);return a/a.sum()


def calibrated_probs(lams,delta):
    rows=[]
    tilt=np.r_[0.,np.asarray(delta,float)]
    for lam in lams:
        p=base_bucket_probs(float(lam))*np.exp(tilt)
        rows.append(p/p.sum())
    return np.asarray(rows)


def fit_tilts(lams,saves,l2,train):
    y=np.array([bucket_index(s) for s in saves],int)
    def fg(b):
        q=calibrated_probs(lams[train],b)
        loss=-np.mean(np.log(np.clip(q[np.arange(len(q)),y[train]],1e-12,1)))+.5*l2*np.dot(b,b)/len(q)
        grad=np.zeros(4)
        # derivative for category intercepts 1..4
        for j in range(1,5):
            grad[j-1]=np.mean(q[:,j]-(y[train]==j))+l2*b[j-1]/len(q)
        return float(loss),grad
    res=minimize(lambda b:fg(b),np.zeros(4),jac=True,method='L-BFGS-B')
    if not res.success: raise RuntimeError(res.message)
    return res.x


def bucket_metrics(lams,saves,delta=None):
    if delta is None:
        q=np.asarray([base_bucket_probs(x) for x in lams])
    else:q=calibrated_probs(lams,delta)
    y=np.array([bucket_index(s) for s in saves],int)
    ll=float(-np.mean(np.log(np.clip(q[np.arange(len(q)),y],1e-12,1))))
    pred_pts=q@np.arange(5)
    actual=np.array([int(s)//3 for s in saves],float)
    e=pred_pts-actual
    return dict(log_loss=ll,save_point_mae=float(np.mean(np.abs(e))),
                save_point_rmse=float(np.sqrt(np.mean(e**2))),save_point_bias=float(np.mean(e)),
                mean_pred_points=float(np.mean(pred_pts)),mean_actual_points=float(np.mean(actual)),
                p3=float(np.mean(q[:,1:].sum(1))),actual_p3=float(np.mean(np.asarray(saves)>=3)),
                p6=float(np.mean(q[:,2:].sum(1))),actual_p6=float(np.mean(np.asarray(saves)>=6)),
                p9=float(np.mean(q[:,3:].sum(1))),actual_p9=float(np.mean(np.asarray(saves)>=9)))


def score(y,p):
    e=np.asarray(p)-np.asarray(y)
    return dict(mae=float(np.mean(np.abs(e))),rmse=float(np.sqrt(np.mean(e**2))),bias=float(np.mean(e)))


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    write_json(OUT/'protocol.json',dict(
      baseline='frozen lambda_saves Poisson',
      candidate='Poisson reweighted across FPL save buckets 0-2/3-5/6-8/9-11/12+',
      development='GW22-27 leave-one-GW-out within reused cohort',
      diagnostic='GW28-38 only; not independent',
      joint='marginal GK update on top of saved DefCon finalist',
      l2_grid=L2,promotion_allowed=False))

    inputs=read_frozen_table(FROZEN,'inputs')
    sides=inputs[['fixture_uuid','team_id','gw','home_team_id','away_team_id','lambda_saves']].drop_duplicates(['fixture_uuid','team_id'])
    # Actual keeper saves are available directly in the frozen raw FPL-core
    # fixture snapshots. Join by GW + home/away identity so no private SQLite
    # artifact is required in CI.
    fx=[]
    for gw in range(22,39):
        p=ROOT/f'data_v1_1/raw/fpl-core-2025-26/GW{gw}/fixtures.csv'
        z=pd.read_csv(p,usecols=['gameweek','home_team','away_team','home_keeper_saves','away_keeper_saves'])
        z=z[z.gameweek==gw].copy()
        fx.append(z)
    sched=pd.concat(fx,ignore_index=True).rename(columns={'gameweek':'gw','home_team':'home_team_id','away_team':'away_team_id'})
    sched['gw']=sched.gw.astype(int);sched['home_team_id']=sched.home_team_id.astype(int);sched['away_team_id']=sched.away_team_id.astype(int)
    sides=sides.merge(sched,on=['gw','home_team_id','away_team_id'],how='left',validate='many_to_one')
    if sides[['home_keeper_saves','away_keeper_saves']].isna().any().any():
        raise ValueError('Missing raw fixture keeper saves')
    sides['actual_saves']=np.where(sides.team_id==sides.home_team_id,sides.home_keeper_saves,sides.away_keeper_saves)
    d=sides.copy()
    if len(d)<200:raise ValueError('Insufficient keeper side rows')

    dev=d.gw.between(22,27).to_numpy();test=d.gw.between(28,38).to_numpy()
    base_dev=bucket_metrics(d.lambda_saves.to_numpy()[dev],d.actual_saves.to_numpy()[dev],None)
    rows=[]
    for l2 in L2:
        oof=np.zeros((dev.sum(),5));dev_idx=np.flatnonzero(dev);pos=0
        for gw in sorted(d.loc[dev,'gw'].unique()):
            tr=dev&(d.gw.to_numpy()!=gw);te=dev&(d.gw.to_numpy()==gw)
            b=fit_tilts(d.lambda_saves.to_numpy(),d.actual_saves.to_numpy(),l2,tr)
            qq=calibrated_probs(d.loc[te,'lambda_saves'].to_numpy(),b)
            n=len(qq);oof[pos:pos+n]=qq;pos+=n
        # reconstruct metrics from q in grouped GW order
        ordered=pd.concat([d[dev&(d.gw.to_numpy()==gw)] for gw in sorted(d.loc[dev,'gw'].unique())],ignore_index=True)
        yy=ordered.actual_saves.to_numpy()
        cats=np.array([bucket_index(s) for s in yy],int)
        ll=float(-np.mean(np.log(np.clip(oof[np.arange(len(oof)),cats],1e-12,1))))
        pred=oof@np.arange(5);act=yy//3;e=pred-act
        rows.append(dict(l2=l2,log_loss=ll,save_point_mae=float(np.mean(abs(e))),
                         save_point_rmse=float(np.sqrt(np.mean(e**2))),save_point_bias=float(np.mean(e))))
    cand=pd.DataFrame(rows).sort_values(['log_loss','save_point_mae']).reset_index(drop=True)
    cand.to_csv(OUT/'development_candidates.csv',index=False)
    best=float(cand.iloc[0].l2)
    final_delta=fit_tilts(d.lambda_saves.to_numpy(),d.actual_saves.to_numpy(),best,dev)
    sel=dict(l2=best,tilts=[0.]+final_delta.tolist(),development_baseline=base_dev)
    write_json(OUT/'selection.json',sel)

    base_test=bucket_metrics(d.lambda_saves.to_numpy()[test],d.actual_saves.to_numpy()[test],None)
    cal_test=bucket_metrics(d.lambda_saves.to_numpy()[test],d.actual_saves.to_numpy()[test],final_delta)
    write_json(OUT/'keeper_bucket_metrics.json',dict(baseline=base_test,calibrated=cal_test,
      delta={k:cal_test[k]-base_test[k] for k in ['log_loss','save_point_mae','save_point_rmse','save_point_bias']}))

    # Joint diagnostic on GW28-38, start from role candidate, replace DC with the
    # saved final DC mu, then add keeper bucket tilts in treatment only.
    role=read_frozen_table(ROLE,'candidate_inputs')
    dc=pd.read_csv(DC)[['fixture_uuid','player_uuid','mu_cal']]
    role=role.merge(dc,on=['fixture_uuid','player_uuid'],how='left',validate='one_to_one')
    role['mu_dc']=role.mu_cal.fillna(role.mu_dc)
    role=role.drop(columns=['mu_cal'])
    truth=read_frozen_table(FROZEN,'targets')

    rec=[]
    tilts=tuple([0.]+final_delta.tolist())
    for i,(fx,g) in enumerate(role[role.gw.between(28,38)].groupby('fixture_uuid',sort=True)):
        _,control=build_pair(g)
        # build_pair candidate only changes minutes. We want identical current
        # role/DC inputs in both arms, then save-bucket calibration in treatment.
        base=control
        treat=replace(base,players=tuple(replace(p,save_bucket_tilts=tilts if p.is_keeper else None) for p in base.players))
        a,b=run_pair(base,treat,n=400,seed=33092501+i)
        for r in g.itertuples():
            rec.append(dict(fixture_uuid=fx,player_uuid=r.player_uuid,gw=r.gw,
                final_dc=a[r.player_uuid]['xPts_nonbonus'],
                final_dc_gk=b[r.player_uuid]['xPts_nonbonus'],
                base_save_points=a[r.player_uuid]['save_points'],
                cal_save_points=b[r.player_uuid]['save_points']))
    pred=pd.DataFrame(rec)
    sc=pred.merge(truth,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    y=sc.total_points-sc.bonus;m0=score(y,sc.final_dc);m1=score(y,sc.final_dc_gk)
    report=dict(classification='reused_split_diagnostic_not_independent_holdout',
      development_gws='22-27',diagnostic_gws='28-38',rows=len(sc),fixtures=int(sc.fixture_uuid.nunique()),
      selected_l2=best,tilts=[0.]+final_delta.tolist(),bucket_metrics={'baseline':base_test,'calibrated':cal_test},
      nonbonus={'final_dc':m0,'final_dc_plus_gk':m1},
      delta_joint={k:m1[k]-m0[k] for k in ['mae','rmse','bias']},
      promoted=False)
    write_json(OUT/'joint_metrics.json',report)
    pred.to_csv(OUT/'joint_predictions.csv.gz',index=False,compression='gzip')
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(sources=[
      dict(path='scripts/run_gk_save_bucket_calibration.py',sha256=sha(Path(__file__))),
      dict(path='src/fpl_v1_1_model/joint_simulator.py',sha256=sha(ROOT/'src/fpl_v1_1_model/joint_simulator.py'))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
