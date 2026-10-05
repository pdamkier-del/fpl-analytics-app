#!/usr/bin/env python3
"""Assemble and test the integrated FPL vFinal candidate.

vFinal components
-----------------
- minutes: combined candidate (performance P(start) + sequence substate + blended sub duration)
- goals/assists: soft-role baseline + selected shared recent-performance allocation
- DefCon: soft-role count + threshold calibration finalist
- goalkeeper saves: frozen baseline (all tested update candidates rejected)
- discipline: frozen yellow/red candidate; own-goal probability used if present in frozen inputs
- penalties: shared team occurrence + taker + conversion + keeper-save event
- BPS: selected role/recent-detail background mean + position-specific residual variance
- historical validation scoring: 2025/26 BPS rules
- live deployment scoring: 2026/27 BPS rules

Comparison is against the frozen current-v4 diagnostic baseline on the same
GW22-38 cohort. This period has been reused throughout development and is NOT an
independent holdout. No production promotion is declared here.
"""
from __future__ import annotations
import json,sys
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.paired_joint import read_frozen_table,build_pair,run_pair
from run_v4_performance_rating_experiment import SOURCE,add_features as add_perf_features
from run_soft_role_performance_allocation import (
    GOAL_BASE,ASSIST_BASE,build_design
)
from run_v4rc_experiment import write_json,sha

FROZEN=ROOT/'analysis/results/deadline-joint-inputs-v1'
ROLE=ROOT/'analysis/results/role-event-priors-20261005-v1'
MINUTES=ROOT/'analysis/results/v4-combined-minutes-20261005-v1/reused_diagnostic_predictions.csv.gz'
PERF_LEDGER=ROOT/'analysis/results/v4-performance-rating-20261005-v1/performance_ledger.csv.gz'
GA=ROOT/'analysis/results/soft-role-performance-allocation-20261005-v1'
DC=ROOT/'analysis/results/defcon-threshold-finalist-20261005-v1/calibrated_dc.csv.gz'
PEN=ROOT/'analysis/results/shared-penalty-joint-20261005-v1/penalty_joint_inputs.csv.gz'
BPS=ROOT/'analysis/results/bps-variance-calibration-20261005-v1/diagnostic_background_distribution.csv.gz'
OUT=ROOT/'analysis/results/vfinal-integrated-20261005-v1'
KEYS=['fixture_uuid','player_uuid','team_id']


def score(y,p):
    e=np.asarray(p,float)-np.asarray(y,float)
    return dict(mae=float(np.mean(np.abs(e))),rmse=float(np.sqrt(np.mean(e**2))),bias=float(np.mean(e)))


def bonus_metrics(actual,p1,p2,p3):
    y=np.asarray(actual,int)
    p=np.c_[1-np.asarray(p1)-np.asarray(p2)-np.asarray(p3),p1,p2,p3]
    p=np.clip(p,1e-9,1);p=p/p.sum(1,keepdims=True)
    eb=p@np.arange(4)
    return dict(
      log_loss=float(-np.mean(np.log(p[np.arange(len(y)),y]))),
      brier=float(np.mean(np.sum((p-np.eye(4)[y])**2,axis=1))),
      mae=float(np.mean(np.abs(eb-y))),
      rmse=float(np.sqrt(np.mean((eb-y)**2))),
      mean_pred=float(np.mean(eb)),mean_actual=float(np.mean(y)),
      p_any=float(np.mean(1-p[:,0])),actual_any=float(np.mean(y>0)))


def apply_perf_rate(frame,base_rate,features,model):
    X=build_design(frame,features,'shared').to_numpy(float)
    Z=(X-np.asarray(model['mean']))/np.asarray(model['scale'])
    return np.maximum(frame[base_rate].to_numpy(float),1e-12)*np.exp(
        np.clip(Z@np.asarray(model['coef']),-4,4))


def normalized_mu(frame,rate,assist=False):
    # Keep the same allocation architecture as the selected GA experiment:
    # expected exposure only normalizes shares; the joint simulator later turns
    # mu/exposure back into on-pitch weights.
    exposure=np.maximum(frame.control_xmins.to_numpy(float)/90,0)
    raw=np.maximum(rate*exposure,1e-12)
    group=(frame.fixture_uuid.astype(str)+'|'+frame.team_id.astype(str)).to_numpy()
    share=np.zeros(len(frame))
    for gid in np.unique(group):
        idx=np.flatnonzero(group==gid);share[idx]=raw[idx]/raw[idx].sum()
    lam=np.where(frame.team_id==frame.home_team_id,frame.lambda_home_goals,frame.lambda_away_goals)
    if assist:
        return lam*frame.assist_probability_per_goal.to_numpy(float)*share
    return lam*share


def build_final_frame():
    role=read_frozen_table(ROLE,'candidate_inputs').sort_values(KEYS).reset_index(drop=True)

    # 1) combined minutes
    mins=pd.read_csv(MINUTES)
    mcols=['fixture_uuid','player_uuid','combined_p_start','combined_q_sub',
           'combined_xmins','combined_sub_minutes']
    role=role.merge(mins[mcols],on=['fixture_uuid','player_uuid'],how='left',validate='one_to_one')
    if role[mcols[2:]].isna().any().any(): raise ValueError('Missing vFinal minute predictions')
    role['v4_workload_start_p_start']=role.combined_p_start
    role['v4_p_cameo_given_bench']=role.combined_q_sub
    role['v4_workload_start_xmins']=role.combined_xmins
    role['v4_cameo_minutes_mean']=role.combined_sub_minutes
    # v4_start_minutes_mean intentionally remains the frozen selected starter duration.

    # 2) role + shared recent-performance goal/assist rates
    feat=pd.read_csv(SOURCE).reset_index(drop=True)
    ledger=pd.read_csv(PERF_LEDGER);ledger.available_at=pd.to_datetime(ledger.available_at,utc=True)
    feat=add_perf_features(feat,ledger)
    extra=sorted(set(GOAL_BASE+ASSIST_BASE))
    role=role.merge(feat[KEYS+extra],on=KEYS,how='left',validate='one_to_one')
    role[extra]=role[extra].fillna(0.)
    models=json.loads((GA/'models.json').read_text())
    gr=apply_perf_rate(role,'goal_rate90',GOAL_BASE,models['goal'])
    ar=apply_perf_rate(role,'assist_rate90',ASSIST_BASE,models['assist'])
    role['goal_mu']=normalized_mu(role,gr,False)
    role['assist_mu']=normalized_mu(role,ar,True)

    # 3) DefCon finalist
    dc=pd.read_csv(DC)[['fixture_uuid','player_uuid','mu_cal']]
    role=role.merge(dc,on=['fixture_uuid','player_uuid'],how='left',validate='one_to_one')
    if role.mu_cal.isna().any(): raise ValueError('Missing DefCon finalist rows')
    role['mu_dc']=role.mu_cal

    # 4) shared penalties
    pen=pd.read_csv(PEN)[['fixture_uuid','player_uuid','lambda_pen','pen_weight',
                          'pen_conversion','team_pen_conversion']]
    role=role.merge(pen,on=['fixture_uuid','player_uuid'],how='left',validate='one_to_one')
    if role[['lambda_pen','pen_weight','pen_conversion','team_pen_conversion']].isna().any().any():
        raise ValueError('Missing shared penalty inputs')

    # 5) BPS mean + variance
    bps=pd.read_csv(BPS)[['fixture_uuid','player_uuid','bg_mean_rate90','bg_sd90']]
    role=role.merge(bps,on=['fixture_uuid','player_uuid'],how='left',validate='one_to_one')
    if role[['bg_mean_rate90','bg_sd90']].isna().any().any():
        raise ValueError('Missing BPS distribution inputs')
    return role


def make_vfinal_input(frame):
    # build_pair applies the modified v4_* minute fields as candidate minutes.
    _,inp=build_pair(frame)
    by=frame.set_index('player_uuid')
    players=[]
    own_available='p_own_goal' in frame.columns
    for p in inp.players:
        r=by.loc[p.player_id]
        kwargs=dict(
          penalty_weight=float(r.pen_weight),
          penalty_conversion=float(r.pen_conversion),
          bps_background_mean=0.0,bps_background_sd=0.0,
          bps_background_rate90=float(r.bg_mean_rate90),
          bps_background_sd90=float(r.bg_sd90))
        if own_available:
            kwargs['p_own_goal']=float(r.p_own_goal)
        players.append(replace(p,**kwargs))
    home=int(frame.home_team_id.iloc[0]);away=int(frame.away_team_id.iloc[0])
    h=frame[frame.team_id==home].iloc[0];a=frame[frame.team_id==away].iloc[0]
    pen_summary=json.loads((ROOT/'analysis/results/shared-penalty-model-20261005-v1/model_summary.json').read_text())
    return replace(inp,players=tuple(players),
      lambda_home_penalties=float(h.lambda_pen),
      lambda_away_penalties=float(a.lambda_pen),
      home_penalty_conversion=float(h.team_pen_conversion),
      away_penalty_conversion=float(a.team_pen_conversion),
      p_penalty_save_given_miss=float(pen_summary['selected']['p_keeper_save_given_miss']),
      bps_rules='2025-26'), own_available


def make_baseline_input(frame):
    # Frozen current-v4 candidate; only switch historical BPS mechanics to
    # correct 2025/26 rules so the comparison is not polluted by wrong-season rules.
    _,inp=build_pair(frame)
    return replace(inp,bps_rules='2025-26')


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    final=build_final_frame()
    base=read_frozen_table(FROZEN,'inputs').sort_values(KEYS).reset_index(drop=True)
    truth=read_frozen_table(FROZEN,'targets')

    # exact cohort identity
    fk=final[['fixture_uuid','player_uuid']].sort_values(['fixture_uuid','player_uuid']).reset_index(drop=True)
    bk=base[['fixture_uuid','player_uuid']].sort_values(['fixture_uuid','player_uuid']).reset_index(drop=True)
    if not fk.equals(bk): raise ValueError('vFinal and baseline cohorts differ')

    rows=[];own_flags=[]
    for i,fx in enumerate(sorted(final.fixture_uuid.unique())):
        fg=final[final.fixture_uuid==fx]
        bg=base[base.fixture_uuid==fx]
        binp=make_baseline_input(bg)
        finp,own=make_vfinal_input(fg);own_flags.append(own)
        rb,rf=run_pair(binp,finp,n=400,seed=39092501+i)
        for r in fg.itertuples(index=False):
            pid=str(r.player_uuid)
            rows.append(dict(
              fixture_uuid=fx,player_uuid=pid,gw=int(r.gw),pos=r.pos,
              baseline_nonbonus=rb[pid]['xPts_nonbonus'],
              vfinal_nonbonus=rf[pid]['xPts_nonbonus'],
              baseline_xpts=rb[pid]['xPts'],
              vfinal_xpts=rf[pid]['xPts'],
              baseline_bonus=rb[pid]['expected_bonus'],
              vfinal_bonus=rf[pid]['expected_bonus'],
              baseline_p1=rb[pid]['p_bonus_1'],baseline_p2=rb[pid]['p_bonus_2'],baseline_p3=rb[pid]['p_bonus_3'],
              vfinal_p1=rf[pid]['p_bonus_1'],vfinal_p2=rf[pid]['p_bonus_2'],vfinal_p3=rf[pid]['p_bonus_3'],
              vfinal_minutes=rf[pid]['expected_minutes'],
              actual_minutes=float(r.minutes) if hasattr(r,'minutes') else np.nan))
    pred=pd.DataFrame(rows)
    sc=pred.merge(truth,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    y_nb=sc.total_points-sc.bonus
    report=dict(
      classification='vFinal integrated candidate; reused GW22-38 diagnostic, not independent holdout',
      season='2025-26',
      fixtures=int(sc.fixture_uuid.nunique()),rows=len(sc),draws_per_fixture=400,
      components=dict(
        minutes='combined candidate',
        goal_assist='soft-role baseline + shared recent performance',
        defcon='soft-role count + threshold calibration finalist',
        goalkeeper='frozen baseline',
        discipline='frozen yellow/red; own-goal probability only if present in frozen candidate input',
        penalties='shared occurrence+taker+conversion+keeper save',
        bps='role+recent-detail mean + position variance; 2025/26 rules for test'),
      own_goal_probability_available=bool(all(own_flags)),
      nonbonus={
        'current_v4':score(y_nb,sc.baseline_nonbonus),
        'vFinal':score(y_nb,sc.vfinal_nonbonus)},
      total_xpts={
        'current_v4_event_bps':score(sc.total_points,sc.baseline_xpts),
        'vFinal':score(sc.total_points,sc.vfinal_xpts)},
      bonus={
        'current_v4_event_bps':bonus_metrics(sc.bonus.astype(int),sc.baseline_p1,sc.baseline_p2,sc.baseline_p3),
        'vFinal':bonus_metrics(sc.bonus.astype(int),sc.vfinal_p1,sc.vfinal_p2,sc.vfinal_p3)},
      promoted=False,
      validation_warning='GW22-38 has been reused for iterative diagnostics; independent validation is still required before production promotion.')
    report['delta_nonbonus']={k:report['nonbonus']['vFinal'][k]-report['nonbonus']['current_v4'][k] for k in ['mae','rmse','bias']}
    report['delta_total_xpts']={k:report['total_xpts']['vFinal'][k]-report['total_xpts']['current_v4_event_bps'][k] for k in ['mae','rmse','bias']}
    report['delta_bonus']={k:report['bonus']['vFinal'][k]-report['bonus']['current_v4_event_bps'][k] for k in ['log_loss','brier','mae','rmse']}

    # by-position diagnostic
    posrows=[]
    for pos,g in sc.groupby('pos'):
        yy=g.total_points-g.bonus
        b=score(yy,g.baseline_nonbonus);v=score(yy,g.vfinal_nonbonus)
        bt=score(g.total_points,g.baseline_xpts);vt=score(g.total_points,g.vfinal_xpts)
        posrows.append(dict(pos=pos,n=len(g),
            baseline_nonbonus_mae=b['mae'],vfinal_nonbonus_mae=v['mae'],delta_nonbonus_mae=v['mae']-b['mae'],
            baseline_total_mae=bt['mae'],vfinal_total_mae=vt['mae'],delta_total_mae=vt['mae']-bt['mae']))
    pd.DataFrame(posrows).to_csv(OUT/'metrics_by_position.csv',index=False)

    # by-GW stability
    gwrows=[]
    for gw,g in sc.groupby('gw'):
        yy=g.total_points-g.bonus
        b=score(yy,g.baseline_nonbonus);v=score(yy,g.vfinal_nonbonus)
        bt=score(g.total_points,g.baseline_xpts);vt=score(g.total_points,g.vfinal_xpts)
        gwrows.append(dict(gw=int(gw),n=len(g),
            baseline_nonbonus_mae=b['mae'],vfinal_nonbonus_mae=v['mae'],delta_nonbonus_mae=v['mae']-b['mae'],
            baseline_total_mae=bt['mae'],vfinal_total_mae=vt['mae'],delta_total_mae=vt['mae']-bt['mae']))
    pd.DataFrame(gwrows).to_csv(OUT/'metrics_by_gw.csv',index=False)

    write_json(OUT/'result.json',report)
    pred.to_csv(OUT/'predictions.csv.gz',index=False,compression='gzip')
    final[['fixture_uuid','player_uuid','team_id','gw','combined_p_start','combined_q_sub','combined_xmins',
           'goal_mu','assist_mu','mu_dc','lambda_saves','lambda_pen','pen_weight','pen_conversion',
           'bg_mean_rate90','bg_sd90']].to_csv(OUT/'vfinal_inputs.csv.gz',index=False,compression='gzip')
    write_json(OUT/'protocol.json',dict(
      baseline='frozen current-v4 candidate on exact same 144-fixture cohort',
      historical_bps_rules='2025-26 in both arms',
      live_bps_rules='2026-27 when deployed',
      diagnostic='GW22-38 reused only',
      draws_per_fixture=400,promotion_allowed=False))

    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(
      sources=[
        dict(path='scripts/run_vfinal_integrated.py',sha256=sha(Path(__file__))),
        dict(path=str(MINUTES.relative_to(ROOT)),sha256=sha(MINUTES)),
        dict(path=str(DC.relative_to(ROOT)),sha256=sha(DC)),
        dict(path=str(PEN.relative_to(ROOT)),sha256=sha(PEN)),
        dict(path=str(BPS.relative_to(ROOT)),sha256=sha(BPS))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
