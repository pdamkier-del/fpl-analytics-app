#!/usr/bin/env python3
"""Test whether recent match performance adds start-probability signal beyond v4.

There is no provider match-rating column in the frozen source. Instead this
experiment uses the rating ingredients already present in historical player
match stats (xG/xA, goals/assists, shots, chances, passing, defensive actions,
GK actions, turnovers) to test the user's underlying hypothesis:

    better recent performance -> higher next-match P(start), conditional on v4.

The test is cutoff-safe: only matches with kickoff+3h < forecast cutoff enter a
player's performance history. The residual correction keeps v4 as an offset and
re-applies the exact-11 team constraint.

This is an exploratory test on GW16-21 and reused GW22-38 diagnostic, not
independent validation.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))

from build_reproducible_role_benchmark import normalize_eleven
from run_v4rc_experiment import fit_v4_start, xmins_from_p, metric_block, sha, write_json

SOURCE=ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz'
RAW=ROOT/'data_v1_1/raw/all-competitions-2025-26'
CLASSIFIED=ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv'
V4_RESULTS=ROOT/'analysis/results/workload-recovered-minutes-v4'
OUT=ROOT/'analysis/results/v4-performance-rating-20261005-v1'
L2=[0.5,2.0,10.0]

LAST_FEATURES=[
 'perf_hist_n','perf_last_minutes','perf_last_goal_assist','perf_last_xgi',
 'perf_last_sot','perf_last_chances','perf_last_dribbles','perf_last_def_actions',
 'perf_last_pass_acc','perf_last_gk_actions','perf_last_goals_prevented',
 'perf_last_goals_conceded','perf_last_dispossessed','perf_last_rating_proxy'
]
RECENT_FEATURES=LAST_FEATURES+[
 'perf_r3_minutes','perf_r3_goal_assist','perf_r3_xgi','perf_r3_sot',
 'perf_r3_chances','perf_r3_dribbles','perf_r3_def_actions','perf_r3_pass_acc',
 'perf_r3_gk_actions','perf_r3_goals_prevented','perf_r3_goals_conceded',
 'perf_r3_dispossessed','perf_r3_rating_proxy','perf_rating_trend'
]
FAMILIES={'last':LAST_FEATURES,'recent3':RECENT_FEATURES}


def read_all(name):
    return pd.concat([pd.read_csv(p) for p in sorted(RAW.glob('GW*/'+name+'.csv'))],ignore_index=True)


def player_id_map():
    line=read_all('lineups')
    clas=pd.read_csv(CLASSIFIED)[['match_id','player_uuid','player']].drop_duplicates()
    starters=line[line.is_starting.astype(str).str.lower().isin(['true','1','yes'])].copy()
    m=starters.merge(clas,left_on=['match_id','player_name'],right_on=['match_id','player'],how='inner')
    pairs=m[['player_id','player_uuid']].dropna().drop_duplicates()
    counts=pairs.groupby('player_id').player_uuid.nunique()
    bad=set(counts[counts>1].index)
    pairs=pairs[~pairs.player_id.isin(bad)]
    pairs=pairs.drop_duplicates('player_id')
    return dict(zip(pairs.player_id.astype(int),pairs.player_uuid.astype(str)))


def build_perf_ledger():
    stats=read_all('playermatchstats')
    matches=read_all('matches')[['match_id','kickoff_time','tournament']].drop_duplicates('match_id')
    mapping=player_id_map()
    stats['player_uuid']=pd.to_numeric(stats.player_id,errors='coerce').map(mapping)
    stats=stats[stats.player_uuid.notna()].copy()
    stats=stats.merge(matches,on='match_id',how='left',validate='many_to_one')
    stats['available_at']=pd.to_datetime(stats.kickoff_time,utc=True,errors='coerce')+pd.Timedelta(hours=3)
    stats=stats[stats.available_at.notna() & (pd.to_numeric(stats.minutes_played,errors='coerce')>0)].copy()

    num=['minutes_played','goals','assists','xg','xa','shots_on_target','chances_created',
         'successful_dribbles','tackles_won','interceptions','recoveries','blocks','clearances',
         'accurate_passes_percent','saves','goals_prevented','goals_conceded','dispossessed']
    for c in num:
        stats[c]=pd.to_numeric(stats[c],errors='coerce').fillna(0.0)
    stats['goal_assist']=stats.goals+stats.assists
    stats['xgi']=stats.xg+stats.xa
    stats['def_actions']=stats.tackles_won+stats.interceptions+stats.recoveries+stats.blocks+stats.clearances
    stats['gk_actions']=stats.saves
    # A provider-agnostic rating-like proxy. It is intentionally simple and is
    # NOT presented as a real SofaScore/FotMob rating. Minutes enter separately.
    stats['rating_proxy']=(4*stats.goals+3*stats.assists+1.5*stats.xg+1.2*stats.xa+
                           .25*stats.shots_on_target+.15*stats.chances_created+
                           .08*stats.def_actions+.20*stats.saves+.70*stats.goals_prevented-
                           .30*stats.goals_conceded-.10*stats.dispossessed)
    keep=['player_uuid','match_id','available_at','tournament','minutes_played','goal_assist','xgi',
          'shots_on_target','chances_created','successful_dribbles','def_actions',
          'accurate_passes_percent','gk_actions','goals_prevented','goals_conceded',
          'dispossessed','rating_proxy']
    stats=stats[keep].sort_values(['player_uuid','available_at','match_id'])
    return stats


def add_features(frame,ledger):
    histories={pid:g for pid,g in ledger.groupby('player_uuid',sort=False)}
    cutoff=pd.to_datetime(frame.cutoff,utc=True)
    rows=[]
    for i,r in frame.iterrows():
        g=histories.get(str(r.player_uuid))
        if g is None:
            past=pd.DataFrame(columns=ledger.columns)
        else:
            past=g[g.available_at<cutoff.iloc[i]].tail(3)
        last=past.tail(1)
        def lv(c):
            return float(last[c].iloc[0]) if len(last) else 0.
        def r3(c):
            if not len(past):return 0.
            # recency weights 1, 1/2, 1/4 from newest backwards
            vals=past[c].to_numpy(float)
            w=2.0**np.arange(len(vals)-1,-1,-1) # oldest higher -- fix below
            w=w[::-1]
            return float(np.average(vals,weights=w))
        # explicit newest-heaviest weights
        def r3(c):
            if not len(past):return 0.
            vals=past[c].to_numpy(float)
            w=np.array([0.25,0.5,1.0])[-len(vals):]
            return float(np.average(vals,weights=w))
        rec={'perf_hist_n':float(len(past)),
             'perf_last_minutes':lv('minutes_played'),
             'perf_last_goal_assist':lv('goal_assist'),'perf_last_xgi':lv('xgi'),
             'perf_last_sot':lv('shots_on_target'),'perf_last_chances':lv('chances_created'),
             'perf_last_dribbles':lv('successful_dribbles'),'perf_last_def_actions':lv('def_actions'),
             'perf_last_pass_acc':lv('accurate_passes_percent'),'perf_last_gk_actions':lv('gk_actions'),
             'perf_last_goals_prevented':lv('goals_prevented'),'perf_last_goals_conceded':lv('goals_conceded'),
             'perf_last_dispossessed':lv('dispossessed'),'perf_last_rating_proxy':lv('rating_proxy'),
             'perf_r3_minutes':r3('minutes_played'),'perf_r3_goal_assist':r3('goal_assist'),
             'perf_r3_xgi':r3('xgi'),'perf_r3_sot':r3('shots_on_target'),
             'perf_r3_chances':r3('chances_created'),'perf_r3_dribbles':r3('successful_dribbles'),
             'perf_r3_def_actions':r3('def_actions'),'perf_r3_pass_acc':r3('accurate_passes_percent'),
             'perf_r3_gk_actions':r3('gk_actions'),'perf_r3_goals_prevented':r3('goals_prevented'),
             'perf_r3_goals_conceded':r3('goals_conceded'),'perf_r3_dispossessed':r3('dispossessed'),
             'perf_r3_rating_proxy':r3('rating_proxy')}
        rec['perf_rating_trend']=rec['perf_last_rating_proxy']-rec['perf_r3_rating_proxy']
        rows.append(rec)
    out=pd.concat([frame.reset_index(drop=True),pd.DataFrame(rows)],axis=1)
    assert np.isfinite(out[RECENT_FEATURES].to_numpy(float)).all()
    return out


def fit_offset(frame,p0,train,features,l2):
    X=frame[features].to_numpy(float)
    mu=X[train].mean(0);sd=X[train].std(0);sd[sd<1e-8]=1
    Z=(X-mu)/sd
    y=frame.y.to_numpy(float)
    off=logit(np.clip(p0,1e-7,1-1e-7))
    Xt=Z[train];yt=y[train];ot=off[train]
    def fg(b):
        z=ot+Xt@b;p=expit(z)
        loss=np.mean(np.logaddexp(0,z)-yt*z)+.5*l2*np.dot(b,b)/len(yt)
        grad=Xt.T@(p-yt)/len(yt)+l2*b/len(yt)
        return float(loss),grad
    res=minimize(lambda b:fg(b),np.zeros(len(features)),jac=True,method='L-BFGS-B')
    if not res.success:raise RuntimeError(res.message)
    raw=expit(off+Z@res.x)
    p=normalize_eleven(frame,raw)
    return p,{'features':features,'l2':l2,'coef':res.x.tolist(),'mean':mu.tolist(),'scale':sd.tolist()}


def metrics(frame,mask,p):
    return metric_block(frame.y.to_numpy()[mask],frame.minutes.to_numpy()[mask],p[mask],xmins_from_p(frame,p)[mask])


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    protocol={
      'question':'Does recent match-performance information improve next-match P(start) beyond v4?',
      'rating_source':'No provider rating exists in frozen source; use rating ingredients + explicit proxy',
      'availability':'only prior player match stats with kickoff+3h < forecast cutoff',
      'development_train':'GW6-15','development_validation':'GW16-21',
      'reused_diagnostic':'GW22-38 only after development selection',
      'families':FAMILIES,'l2':L2,
      'selection':'lowest development start log-loss, must not worsen xMins RMSE by >0.05; otherwise v4',
      'warning':'exploratory; requires independent validation before promotion'
    }
    write_json(OUT/'protocol.json',protocol)

    frame=pd.read_csv(SOURCE).reset_index(drop=True)
    ledger=build_perf_ledger()
    frame=add_features(frame,ledger)
    ledger.to_csv(OUT/'performance_ledger.csv.gz',index=False,compression='gzip')

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev=frame.gw.between(16,21).to_numpy()
    cut=pd.to_datetime(frame.loc[dev,'cutoff'],utc=True).min()
    tr=(frame.gw.between(6,15)&(known<cut)).to_numpy()
    p0,_=fit_v4_start(frame,tr)
    base=metrics(frame,dev,p0)

    rows=[];models={};preds={}
    for fam,features in FAMILIES.items():
        for l2 in L2:
            p,m=fit_offset(frame,p0,tr,features,l2)
            met=metrics(frame,dev,p)
            rows.append({'candidate':fam,'l2':l2,**met,
                         'delta_log_loss':met['log_loss']-base['log_loss'],
                         'delta_brier':met['brier']-base['brier'],
                         'delta_xmins_mae':met['xmins_mae']-base['xmins_mae'],
                         'delta_xmins_rmse':met['xmins_rmse']-base['xmins_rmse']})
            models[f'{fam}_{l2:g}']=m;preds[(fam,l2)]=p
    cand=pd.DataFrame(rows).sort_values(['log_loss','xmins_rmse','candidate','l2'])
    ok=cand[cand.delta_xmins_rmse<=0.05]
    if len(ok) and ok.iloc[0].log_loss<base['log_loss']-1e-10:
        best=ok.iloc[0];sel=str(best.candidate);sell2=float(best.l2)
    else:sel='v4';sell2=None
    cand.to_csv(OUT/'development_candidates.csv',index=False)
    write_json(OUT/'selection.json',{'v4':base,'selected':sel,'selected_l2':sell2})
    write_json(OUT/'development_models.json',models)

    # Final fit and reused diagnostic.
    test=frame.gw.between(22,38).to_numpy()
    cut2=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
    tr2=(frame.gw.between(6,21)&(known<cut2)).to_numpy()
    pbase,_=fit_v4_start(frame,tr2)
    if sel=='v4':
        pnew=pbase.copy();fmodel=None
    else:
        pnew,fmodel=fit_offset(frame,pbase,tr2,FAMILIES[sel],sell2)
    b=metrics(frame,test,pbase);n=metrics(frame,test,pnew)

    # Slices: ambiguous starters and status transitions.
    changed=(frame.role_started_last_gw.to_numpy(float)>0.5)!=(frame.y.to_numpy(int)>0) # posthoc diagnostic only
    bands=[
      ('all',test),
      ('pstart_0.20_0.80',test&(pbase>=.2)&(pbase<=.8)),
      ('has_performance_history',test&(frame.perf_hist_n.to_numpy()>0)),
      ('POSTHOC_start_status_changed',test&changed)
    ]
    sr=[]
    for label,m in bands:
        if not m.any():continue
        sr.append({'slice':label,'arm':'v4',**metrics(frame,m,pbase)})
        sr.append({'slice':label,'arm':'v4_performance',**metrics(frame,m,pnew)})
    pd.DataFrame(sr).to_csv(OUT/'diagnostic_slices.csv',index=False)

    # Coefficients for interpretability.
    if fmodel:
        coef=pd.DataFrame({'feature':fmodel['features'],'coefficient':fmodel['coef']})
        coef['abs_coefficient']=coef.coefficient.abs()
        coef.sort_values('abs_coefficient',ascending=False).to_csv(OUT/'selected_coefficients.csv',index=False)

    result={
      'classification':'performance/rating-proxy exploratory test',
      'development':{'v4':base,'selected':sel,'selected_l2':sell2},
      'reused_diagnostic':{'v4':b,'candidate':n,
        'delta_candidate_minus_v4':{k:n[k]-b[k] for k in ['brier','log_loss','xmins_mae','xmins_rmse','xmins_bias']}},
      'provider_match_rating_available':False,
      'performance_ledger_rows':int(len(ledger)),
      'mapped_players':int(ledger.player_uuid.nunique()),
      'promoted':False
    }
    write_json(OUT/'result.json',result)
    write_json(OUT/'frozen_model.json',{'selected':sel,'model':fmodel})
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',{
      'sources':[{'path':str(SOURCE.relative_to(ROOT)),'sha256':sha(SOURCE)},
                 {'path':str(CLASSIFIED.relative_to(ROOT)),'sha256':sha(CLASSIFIED)},
                 {'path':'scripts/run_v4_performance_rating_experiment.py','sha256':sha(Path(__file__))}],
      'outputs':[{'path':p.name,'sha256':sha(p)} for p in outs]})
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
