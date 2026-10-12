#!/usr/bin/env python3
"""Isolated role-hierarchy time decay: match-count vs true calendar elapsed days.

Compares exact q/H geometry (same role histories and actual past games) with
the only alteration being the decay of historic role evidence.
Baseline: 2^(-match_index / 3 or 10).
Calendar candidate: 2^(-actual_elapsed_days / (7*3 or 7*10)).
Testing as a PL-only standalone P(start) and xM model, NOT full frozen MM
(which also includes European/cup matches, XI optimizer, performance offsets,
substitute-duration fitting etc). No model promotion can follow this proxy.
"""
from __future__ import annotations
import json,sys
from collections import defaultdict
from math import log
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.role_history import RoleHistory,summarize_state
from fpl_v1_1_model.role_classifier import ROLES
from fpl_v1_1_model.workload import WORKLOAD_FEATURES
from build_reproducible_role_benchmark import BASE_FEATURES,ROLE_FEATURES,normalize_eleven
from run_mm_unified_official_roles import SOURCE,CLASSIFIED
from fpl_v1_1_model.team_news_history import read_split_gzip_jsonl,build_strict_team_news_features
from run_mm_v2_team_news_availability_experiment import policy_caps
from fpl_v1_1_model.availability_projection import project_exact_starters_with_caps
OUT=ROOT/'work/live-final-model/mm_role_calendar_vs_game_lag.json'
NEWS=ROOT/'data_v1_1/derived/team_news_audit/2025-26-v2'

class CalendarRoleHistory(RoleHistory):
    def __init__(self,mode):
        super().__init__();self.mode=mode
    def state(self,team,cutoff,half_life=10,q_importance_scale=0.0,h_importance_scale=0.0,importance_floor=0.35):
        games=self.before(team,cutoff)
        minutes=defaultdict(lambda:defaultdict(float));starts=defaultdict(lambda:defaultdict(float))
        totals=defaultdict(float);cap_mass=defaultdict(float);den=0.;players=set()
        disagreements=defaultdict(float);appearance_evidence=defaultdict(float)
        qis=max(0.,min(1.,float(q_importance_scale)))
        his=max(0.,min(1.,float(h_importance_scale)))
        floor=max(0.,min(1.,float(importance_floor)))
        latest=pd.Timestamp(games[-1]['known_at']) if games else pd.Timestamp(cutoff)
        for lag,g in enumerate(reversed(games)):
            if self.mode=='match_lag':
                weight=2**(-lag/half_life)
            else:
                latest_ref=latest if self.mode=='calendar_relative' else pd.Timestamp(cutoff)
                days=(latest_ref-pd.Timestamp(g['known_at'])).total_seconds()/86400.
                if days<0:raise ValueError('Future role event included')
                weight=2**(-days/(half_life*7.))
            imp=floor+(1.-floor)*max(0.,min(1.,float(g.get('importance',1.))))
            qw=weight*((1.-qis)+qis*imp);hw=weight*((1.-his)+his*imp)
            den+=hw
            for p in g['players']:
                pid=str(p['player_uuid']);role=p.get('role')
                players.add(pid)
                if role not in ROLES or not p.get('started'):continue
                minutes[pid][role]+=qw*min(1.35,max(0.,float(p['minutes']))/90)
                starts[pid][role]+=hw;totals[role]+=hw;cap_mass[role]+=hw
                disagreements[pid]+=qw*bool(p.get('disagreement'))
                appearance_evidence[pid]+=qw
        capacities={r:cap_mass[r]/den if den else 0. for r in ROLES}
        states={}
        for pid in players:
            mass=minutes[pid];seen=[r for r in mass if mass[r]>0]
            if not seen:
                states[pid]={'q':{},'H':{},'evidence':0.,'disagreement_share':0.};continue
            allowed=['GK'] if seen==['GK'] else [r for r in ROLES if r!='GK']
            qden=sum(mass.get(r,0.)+.05 for r in allowed)
            q={r:(mass.get(r,0.)+.05)/qden for r in allowed}
            H={}
            for role in allowed:
                candidates=sum(1 for other in players if starts[other].get(role,0)>0)
                hden=totals[role]+.1*max(1,candidates)
                H[role]=min(.995,capacities[role]*(starts[pid].get(role,0.)+.1)/hden) if starts[pid].get(role,0.)>0 and hden else 0.
            states[pid]={'q':q,'H':H,'evidence':sum(mass.values()),
                         'disagreement_share':disagreements[pid]/appearance_evidence[pid] if appearance_evidence[pid] else 0.}
        return states,capacities,games

def build_PL_history():
    classified=pd.read_csv(CLASSIFIED,low_memory=False)
    actual=pd.read_csv(ROOT/'analysis/results/reproducible-role-v1/all_feature_predictions.csv.gz',
         usecols=['fixture_uuid','player_uuid','minutes','y'],low_memory=False).drop_duplicates()
    classified=classified.merge(actual,on=['fixture_uuid','player_uuid'],how='left',validate='one_to_one')
    classified=classified[classified.match_id.astype(str).str.contains('25-26-prem-')].copy()
    classified['kickoff']=pd.to_datetime(classified.kickoff,utc=True,errors='raise')
    if not {'final_role','team_id','player_uuid','disagreement'}.issubset(classified):
        raise ValueError('No classified official role evidence')
    games=[]
    for (match,team),group in classified.groupby(['match_id','team_id']):
        if group.kickoff.nunique()!=1:raise AssertionError('Kickoff mismatch')
        ko=group.kickoff.iloc[0]
        players=[dict(player_uuid=str(r.player_uuid),role=str(r.final_role),
                      started=bool(r.y) if pd.notna(r.y) else False,
                      minutes=float(r.minutes) if pd.notna(r.minutes) else 0.,
                      disagreement=bool(r.disagreement))
            for r in group.itertuples(index=False)]
        if len(players)!=11:continue
        games.append(dict(team_id=int(team),match_id=str(match),
                          known_at=ko+pd.Timedelta(hours=3),players=players))
    if not 700<=len(games)<=760:raise AssertionError('Incomplete 2025/26 PL historical role games '+str(len(games)))
    return games

def features(frame,games,mode):
    hist=CalendarRoleHistory(mode)
    for r in games:
        hist.add_game(r['team_id'],r['known_at'],r['match_id'],r['players'])
    cache={};rows=[]
    for v in frame.itertuples(index=False):
        cutoff=pd.Timestamp(v.cutoff);key=(int(v.team_id),str(cutoff))
        if key not in cache:
            cache[key]={speed:hist.state(int(v.team_id),cutoff,half)
                        for speed,half in [('fast',3),('slow',10)]}
        rec={}
        for speed in ('fast','slow'):
            states,caps,known=cache[key][speed];st=states.get(str(v.player_uuid),{})
            for k,val in summarize_state(st,caps).items():
                if k.startswith('role_'):rec[f'{k}_{speed}']=float(val)
            if speed=='slow':
                q=st.get('q',{})
                rec['role_started_last_gw']=float(bool(known and any(
                    str(p['player_uuid'])==str(v.player_uuid) and p.get('started')
                    for p in known[-1]['players'])))
        rows.append(rec)
    x=pd.DataFrame(rows,index=frame.index)
    for c in ROLE_FEATURES:
        if c not in x:x[c]=0.
    if not np.isfinite(x[ROLE_FEATURES].to_numpy(float)).all():raise ValueError('Nonfinite role history')
    return x[ROLE_FEATURES]

def assess(frame,model_features,train,mask,caps):
    model=make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,random_state=0))
    cols=BASE_FEATURES+ROLE_FEATURES+WORKLOAD_FEATURES
    model.fit(model_features.loc[train,cols],frame.loc[train,'y'])
    raw=model.predict_proba(model_features[cols])[:,1]
    p=normalize_eleven(frame,raw)
    # Same hard and soft caps in both variants.
    p=project_exact_starters_with_caps(frame,p,caps)
    b=frame.p_cameo_given_bench.to_numpy(float)*frame.cameo_minutes_mean.to_numpy(float)
    xm=p*frame.start_minutes_mean.to_numpy(float)+(1-p)*b
    y=frame.loc[mask,'y'].to_numpy(float);minutes=frame.loc[mask,'minutes'].to_numpy(float)
    pp=np.clip(p[mask],1e-9,1-1e-9)
    e=xm[mask]-minutes
    report=dict(n=int(mask.sum()),start_logloss=float(-np.mean(y*np.log(pp)+(1-y)*np.log(1-pp))),
         start_brier=float(np.mean((pp-y)**2)),
         xmins_mae=float(np.mean(np.abs(e))),xmins_rmse=float(np.sqrt(np.mean(e*e))))
    return report

def main():
    frame=pd.read_csv(SOURCE,low_memory=False).reset_index(drop=True)
    frame=build_strict_team_news_features(frame,
        read_split_gzip_jsonl(NEWS,'predeadline_strict.jsonl.gz'))
    caps=policy_caps(frame,'soft_0.5_0.1')
    games=build_PL_history()
    cols=BASE_FEATURES+ROLE_FEATURES+WORKLOAD_FEATURES
    for c in cols:
        if c not in frame:raise AssertionError('Missing source covariate: '+c)
    variants=['match_lag','calendar_relative','calendar_absolute']
    extra={}
    for name in variants:
        role=features(frame,games,name)
        a=frame.copy()
        for c in ROLE_FEATURES:a[c]=role[c]
        extra[name]=a
    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev=frame.gw.between(16,21).to_numpy()
    devcut=pd.to_datetime(frame.loc[dev,'cutoff'],utc=True).min()
    train=(frame.gw.between(6,15)&known.lt(devcut)).to_numpy()
    results={}
    for name in variants:
        v=assess(frame,extra[name],train,dev,caps)
        results[name]={'dev':v}
        print('ROLE_TIME_MM_DEV',json.dumps(dict(variant=name,**v)),flush=True)
    orig=results['match_lag']['dev']
    eligible=[name for name in variants[1:] if
              results[name]['dev']['start_logloss']<orig['start_logloss'] and
              results[name]['dev']['xmins_mae']<=orig['xmins_mae']+.03 and
              results[name]['dev']['xmins_rmse']<=orig['xmins_rmse']+.03]
    choice=min(eligible,key=lambda k:(results[k]['dev']['start_logloss'],results[k]['dev']['xmins_rmse'])) if eligible else 'match_lag'
    test=frame.gw.between(22,38).to_numpy()
    testcut=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
    fit=(frame.gw.between(6,21)&known.lt(testcut)).to_numpy()
    for name in ['match_lag']+([choice] if choice!='match_lag' else []):
        v=assess(frame,extra[name],fit,test,caps)
        results[name]['reused_test']=v
        print('ROLE_TIME_MM_REUSED',json.dumps(dict(variant=name,**v)),flush=True)
    out=dict(classification='RESEARCH_ISOLATED_PL_ROLE_DECAY_NOT_FULL_MM',
       sources=dict(pl_confirmed_starter_team_sides=len(games),rows=len(frame)),
       variants=dict(match_lag='half-life 3 or 10 matches',
         calendar_relative='half-life 21 or 70 days measured backwards from latest known PL match',
         calendar_absolute='half-life 21 or 70 days measured backwards from current deadline'),
       dev='GW6-15 train -> GW16-21',diagnostic='GW6-21 train -> GW22-38 reused',
       results=results,selected_dev_only=choice,
       caveats=['Uses PL role evidence only, missing certified cup and European role history',
                'Uses baseline logistic with soft availability caps, not full performance/XI/conditional minutes MM',
                'Scoring GW22-38 is reused diagnostic, not a fresh independent holdout'],
       promoted=False,app_changed=False)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,indent=2)+'\n')
    print('ROLE_TIME_MM_SELECTION',json.dumps(dict(selected=choice,results=results)),flush=True)
if __name__=='__main__':main()
