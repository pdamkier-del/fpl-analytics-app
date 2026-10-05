#!/usr/bin/env python3
"""Calibrate background-BPS variance for the selected mean model.

The selected conditional mean is frozen from the previous BPS experiment
(role + recent detailed actions, half-life 3, L2=200). This step calibrates only
the residual uncertainty used inside match-level BPS ranking.

Variance candidates are fit on GW16-21 only:
- zero: deterministic background (current candidate)
- global: one residual sd90
- position: GK/DEF/MID/FWD residual sd90 shrunk toward global

Residual scaling matches the simulator:
  total_background ~ N(rate90 * m/90, sd90 * sqrt(m/90)).

Selection criterion is Gaussian residual NLL on development; no bonus outcomes
from GW22-38 are used for selection. The chosen variance is then tested on the
reused GW22-38 joint diagnostic with 2025/26 BPS rules.

No automatic production promotion.
"""
from __future__ import annotations
import json,sys,math
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.paired_joint import read_frozen_table,build_pair,run_pair
from run_bps_background_experiment import (
    actual_background_ledger,feature_frame,apply_model,prepare_integrated_candidate,
    with_bps,multiclass_bonus_metrics,score,KEYS,SOURCE,ROLE,DC,FROZEN,OUT as PREV_OUT
)
from run_v4_performance_rating_experiment import CLASSIFIED
from run_v4rc_experiment import write_json,sha

OUT=ROOT/'analysis/results/bps-variance-calibration-20261005-v1'
TAU_POS=80.0


def gaussian_nll(resid,var):
    var=np.maximum(np.asarray(var,float),1e-9);r=np.asarray(resid,float)
    return float(np.mean(.5*(np.log(2*np.pi*var)+r*r/var)))


def fit_sigmas(df,rate):
    frac=np.clip(df.minutes_played.to_numpy(float)/90.0,1/90,1)
    resid=df.bg2025_proxy.to_numpy(float)-rate*frac
    # Simulator variance is sd90^2 * frac => standardized residual per sqrt(frac).
    z=resid/np.sqrt(frac)
    global_var=float(np.mean(z*z))
    global_sd=float(np.sqrt(max(global_var,1e-9)))
    pos=df.pos.replace({'GKP':'GK'}).astype(str).to_numpy()
    pvar={}
    psd={}
    for p in ['GK','DEF','MID','FWD']:
        mask=pos==p
        n=float(mask.sum())
        raw=float(np.mean(z[mask]**2)) if mask.any() else global_var
        shr=(n*raw+TAU_POS*global_var)/(n+TAU_POS)
        pvar[p]=shr;psd[p]=float(np.sqrt(max(shr,1e-9)))
    nll_global=gaussian_nll(resid,global_var*frac)
    nll_pos=gaussian_nll(resid,np.array([pvar.get(p,global_var) for p in pos])*frac)
    return dict(global_sd90=global_sd,position_sd90=psd,
                development_nll={'global':nll_global,'position':nll_pos},
                residual_mean=float(np.mean(resid)),residual_rmse=float(np.sqrt(np.mean(resid**2))),
                n=int(len(df)))


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    OUT.mkdir(parents=True)

    prev=json.loads((PREV_OUT/'selection.json').read_text())
    sel=prev['selected'];model=sel['model'];half=float(sel['half'])

    ledger=actual_background_ledger()
    dev=read_frozen_table(ROLE,'development_prior_predictions')
    dev=dev[dev.tau==900].copy().reset_index(drop=True)
    allf=pd.read_csv(SOURCE)
    # use role cols from selected model; q cols are whatever feature_frame needs
    from fpl_v1_1_model.role_classifier import ROLES
    qcols=['q_'+r+'_slow' for r in ROLES]
    featcols=KEYS+['cutoff','pos']+qcols
    base=dev.merge(allf[featcols],on=KEYS,how='left',validate='one_to_one',suffixes=('','_f'))
    if 'pos_f' in base: base['pos']=base.pos.fillna(base.pos_f)
    actual=ledger[['fixture_uuid','player_uuid','minutes_played','bg2025_proxy']].drop_duplicates(['fixture_uuid','player_uuid'])
    base=base.merge(actual,on=['fixture_uuid','player_uuid'],how='inner',validate='one_to_one')
    base=base[base.minutes_played>0].reset_index(drop=True)
    fdev=feature_frame(base,half,ledger)
    rate=np.clip(apply_model(fdev,model),
                 float(np.quantile((base.bg2025_proxy*90/np.maximum(base.minutes_played,1)),.01)),
                 float(np.quantile((base.bg2025_proxy*90/np.maximum(base.minutes_played,1)),.99)))
    varfit=fit_sigmas(fdev,rate)

    selected='position' if varfit['development_nll']['position'] < varfit['development_nll']['global'] else 'global'
    write_json(OUT/'variance_fit.json',dict(selected=selected,tau_position=TAU_POS,**varfit))

    # Rebuild final candidate mean rates for reused diagnostic.
    role,psave=prepare_integrated_candidate()
    cand=role.merge(allf[featcols],on=KEYS,how='left',validate='one_to_one',suffixes=('','_f'))
    if 'pos_f' in cand: cand['pos']=cand.pos.fillna(cand.pos_f)
    fcand=feature_frame(cand,half,ledger)
    meanrate=apply_model(fcand,model)
    lo=float(np.quantile(rate,.01));hi=float(np.quantile(rate,.99))
    meanrate=np.clip(meanrate,lo,hi)
    fcand['bg_mean_rate90']=meanrate
    broad=fcand.pos.replace({'GKP':'GK'}).astype(str)
    if selected=='position':
        fcand['bg_sd90']=[varfit['position_sd90'].get(p,varfit['global_sd90']) for p in broad]
    else:
        fcand['bg_sd90']=varfit['global_sd90']

    truth=read_frozen_table(FROZEN,'targets')
    rec=[]
    for i,(fx,g) in enumerate(fcand[fcand.gw.between(22,38)].groupby('fixture_uuid',sort=True)):
        _,raw=build_pair(g)
        mean_lookup=dict(zip(g.player_uuid.astype(str),g.bg_mean_rate90))
        sd_lookup=dict(zip(g.player_uuid.astype(str),g.bg_sd90))
        # deterministic selected mean = previous finalist
        det=with_bps(raw,g,mean_lookup,psave)
        # variance candidate
        home=int(g.home_team_id.iloc[0]);away=int(g.away_team_id.iloc[0])
        hrow=g[g.team_id==home].iloc[0];arow=g[g.team_id==away].iloc[0]
        bypid=g.set_index('player_uuid')
        players=[]
        for p in det.players:
            row=bypid.loc[p.player_id]
            players.append(replace(p,bps_background_rate90=float(row.bg_mean_rate90),
                                   bps_background_sd90=float(sd_lookup[p.player_id])))
        varinp=replace(det,players=tuple(players))
        a,b=run_pair(det,varinp,n=360,seed=38092501+i)
        for r in g.itertuples():
            pid=str(r.player_uuid)
            rec.append(dict(fixture_uuid=fx,player_uuid=pid,gw=r.gw,
                det_bonus=a[pid]['expected_bonus'],var_bonus=b[pid]['expected_bonus'],
                det_p1=a[pid]['p_bonus_1'],det_p2=a[pid]['p_bonus_2'],det_p3=a[pid]['p_bonus_3'],
                var_p1=b[pid]['p_bonus_1'],var_p2=b[pid]['p_bonus_2'],var_p3=b[pid]['p_bonus_3'],
                det_xpts=a[pid]['xPts'],var_xpts=b[pid]['xPts']))
    pred=pd.DataFrame(rec);sc=pred.merge(truth,on=['fixture_uuid','player_uuid'],validate='one_to_one')

    report=dict(
      classification='reused_diagnostic_not_independent_holdout',
      variance_selected=selected,development_variance_fit=varfit,
      fixtures=int(sc.fixture_uuid.nunique()),rows=len(sc),draws_per_fixture=360,
      bonus={
        'deterministic_mean':multiclass_bonus_metrics(sc.bonus.astype(int),sc.det_p1,sc.det_p2,sc.det_p3),
        'variance_calibrated':multiclass_bonus_metrics(sc.bonus.astype(int),sc.var_p1,sc.var_p2,sc.var_p3)},
      total_xpts={
        'deterministic_mean':score(sc.total_points,sc.det_xpts),
        'variance_calibrated':score(sc.total_points,sc.var_xpts)},
      promoted=False)
    report['delta_bonus']={k:report['bonus']['variance_calibrated'][k]-report['bonus']['deterministic_mean'][k]
        for k in ['log_loss','brier','expected_bonus_mae','expected_bonus_rmse','mean_pred_bonus','p_any']}
    report['delta_xpts']={k:report['total_xpts']['variance_calibrated'][k]-report['total_xpts']['deterministic_mean'][k]
        for k in ['mae','rmse','bias']}
    write_json(OUT/'joint_metrics.json',report)
    pred.to_csv(OUT/'joint_predictions.csv.gz',index=False,compression='gzip')
    fcand[['fixture_uuid','player_uuid','gw','bg_mean_rate90','bg_sd90']].to_csv(
        OUT/'diagnostic_background_distribution.csv.gz',index=False,compression='gzip')
    write_json(OUT/'protocol.json',dict(
      mean_model='frozen previous BPS selected mean',
      variance_selection='GW16-21 residual Gaussian NLL only',
      reused_diagnostic='GW22-38 bonus/xP',
      simulator_scaling='sd_total = sd90 * sqrt(minutes/90)',
      promotion_allowed=False))
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(sources=[
      dict(path='scripts/run_bps_variance_calibration.py',sha256=sha(Path(__file__))),
      dict(path='analysis/results/bps-background-20251005-v1/selection.json',sha256=sha(PREV_OUT/'selection.json'))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
