#!/usr/bin/env python3
"""Past-only historical test: are individual xG/xA shares too concentrated?

This is a structural/conditional allocation proxy, NOT the frozen historical PM:
- 2025/26 PL only; GW6-21 selects ex ante power gamma; GW22-38 held out.
- Uses ACTUAL played minutes and available player lineups, not predicted MM.
  This intentionally removes minutes uncertainty to isolate allocation; it
  must not be represented as a live xP accuracy test.
- Pre-GW player-rate history only; source xG/xA from the same FotMob archive.
- No model changes, no future outcomes added to past, no production promotion.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data_v1_1/raw/all-competitions-2025-26'
GAMMAS=[0.7,0.85,1.0,1.15,1.3]
TAU_MINUTES=900.
rng=np.random.default_rng(20261012)

def read():
    games=[];players=[];lineups=[]
    for gw in range(1,39):
        base=RAW/f'GW{gw}'
        def filter_pl(name):
            data=pd.read_csv(base/name,low_memory=False)
            return data[data.match_id.astype(str).str.startswith('25-26-prem-')].copy()
        games.append(filter_pl('matches.csv'))
        players.append(filter_pl('playermatchstats.csv'))
        lineups.append(filter_pl('lineups.csv'))
    m=pd.concat(games,ignore_index=True).drop_duplicates('match_id')
    p=pd.concat(players,ignore_index=True).drop_duplicates(['match_id','player_id'])
    l=pd.concat(lineups,ignore_index=True)
    l=l.dropna(subset=['player_id','team_side'])
    l=l.drop_duplicates(['match_id','player_id'])
    # Team-side is essential. Do not guess a team from the player name.
    p['player_id']=pd.to_numeric(p.player_id,errors='coerce')
    l['player_id']=pd.to_numeric(l.player_id,errors='coerce')
    p=p.merge(l[['match_id','player_id','team_side','team_code','position']],on=['match_id','player_id'],
              how='left',validate='one_to_one')
    m['gw']=pd.to_numeric(m.gameweek,errors='coerce')
    p=p.merge(m[['match_id','gw','home_score','away_score','finished']],on='match_id',
              how='inner',validate='many_to_one')
    total=len(p)
    p['minutes']=pd.to_numeric(p.minutes_played,errors='coerce')
    for col in ['xg','xa','goals','assists']:
        p[col]=pd.to_numeric(p[col],errors='coerce')
    p=p[(p.minutes>0)&(p.minutes<=130)&p.team_side.isin(['home','away'])&
        p.position.isin(['G','D','M','F'])&p[['xg','xa','goals','assists']].notna().all(axis=1)&
        p.gw.notna()&(p.finished.astype(str).str.lower()=='true')].copy()
    p['gw']=p.gw.astype(int)
    # Complete both sides: 11+ players, excluding missing xG/xA that must not become zeros.
    side=p.groupby(['match_id','team_side']).agg(n=('player_id','nunique'))
    side=side[side.n>=11]
    matches=side.reset_index().groupby('match_id').team_side.nunique()
    complete=set(matches[matches==2].index)
    p=p[p.match_id.isin(complete)].copy()
    if p.match_id.nunique()<300:raise ValueError(f'Incomplete historical PL coverage {p.match_id.nunique()} matches')
    if p.duplicated(['match_id','player_id']).any():raise ValueError('player fixtures duplicated')
    assert p.gw.min()<=1 and p.gw.max()==38
    return p,dict(source_player_rows=total,covered_players=len(p),covered_matches=p.match_id.nunique(),
                  covered_team_sides=len(side[side.index.get_level_values(0).isin(complete)]))

def per_event(frame,event,gamma):
    q=frame.copy()
    q['group']=q.match_id.astype(str)+'|'+q.team_side.astype(str)
    # Probabilities must include all on-pitch players; no target xG/xA used.
    w=np.maximum(q[f'{event}_lag_rate90'].to_numpy(float)*q.minutes.to_numpy(float)/90.,1e-12)
    w=w**gamma
    q['weight']=w
    q['prob']=w/q.groupby('group').weight.transform('sum').to_numpy(float)
    q['contribution']=-q[event].to_numpy(float)*np.log(np.clip(q.prob.to_numpy(float),1e-12,1))
    return q.groupby(['match_id','gw'],as_index=False).agg(loss=('contribution','sum'),mass=(event,'sum'),
                                                         sides=('team_side','nunique'))

def score(values):
    return float(values.loss.sum()/values.mass.sum())

def main():
    p,cov=read()
    records=[]
    for gw in range(6,39):
        hist=p[p.gw<gw]
        future=p[p.gw==gw].copy()
        if future.empty:continue
        groups=hist.groupby('position').agg(minutes=('minutes','sum'),xg=('xg','sum'),xa=('xa','sum'))
        by_id=hist.groupby('player_id').agg(minutes=('minutes','sum'),xg=('xg','sum'),xa=('xa','sum'))
        assert (by_id.minutes>0).all()
        for event in ['xg','xa']:
            prior=(90*groups[event]/groups.minutes).to_dict()
            e='goal' if event=='xg' else 'assist'
            prior_vals=future.position.map(prior).fillna(90*hist[event].sum()/hist.minutes.sum()).to_numpy(float)
            player=future.player_id.map(by_id[event]).fillna(0.).to_numpy(float)
            minutes=future.player_id.map(by_id.minutes).fillna(0.).to_numpy(float)
            future[f'{event}_lag_rate90']=(90*player+TAU_MINUTES*prior_vals)/(minutes+TAU_MINUTES)
            # Prevent an in-sample target from entering its own earlier rate.
            assert np.isfinite(future[f'{event}_lag_rate90']).all()
            for gamma in GAMMAS:
                d=per_event(future,event,gamma)
                d['event']=e
                d['gamma']=gamma
                records.append(d)
    data=pd.concat(records,ignore_index=True)
    reports={}
    for event in ['goal','assist']:
        t=data[data.event==event]
        dev=t[t.gw.between(6,21)]
        hold=t[t.gw.between(22,38)]
        devs={str(g):round(score(dev[dev.gamma==g]),7) for g in GAMMAS}
        best=min(GAMMAS,key=lambda g:score(dev[dev.gamma==g]))
        hs={str(g):round(score(hold[hold.gamma==g]),7) for g in GAMMAS}
        base=hs['1.0'];score_best=hs[str(best)]
        # Block bootstrap whole match: avoids pretending individual players independent.
        pivot=hold[hold.gamma.isin([1.,best])].pivot_table(index='match_id',columns='gamma',values=['loss','mass'],aggfunc='sum')
        m=pivot['mass'][1.0].to_numpy(float)
        d=pivot['loss'][best].to_numpy(float)-pivot['loss'][1.0].to_numpy(float)
        # Multiple gamma branches can be same if best 1.0.
        n=len(m)
        boots=[]
        for _ in range(1000):
            idx=rng.integers(0,n,n)
            boots.append(float(d[idx].sum()/m[idx].sum()))
        lo,hi=np.quantile(boots,[.025,.975])
        reports[event]=dict(chosen_gamma=best,dev=devs,holdout=hs,
                            holdout_delta=round(score_best-base,7),
                            holdout_matches=int(len(pivot)),
                            bootstrap_delta_95CI=[round(float(lo),7),round(float(hi),7)],
                            improves=bool(score_best<base),
                            direction='negative_is_better')
        print('SHARE_TEST_'+event.upper(),json.dumps(reports[event]))
    x=p.groupby(['match_id','team_side']).agg(goals=('goals','sum'),assists=('assists','sum'),xg=('xg','sum'),xa=('xa','sum'))
    goal=float(x.goals.sum());ass=float(x.assists.sum())
    results=dict(classification='ISOLATED_HISTORICAL_ORACLE_MINUTES_ALLOCATION_PROXY_NOT_FROZEN_PM',
                 coverage=cov,source='2025/26 FotMob Premier League player xG/xA + lineups',
                 outcome_source='postmatch xG/xA, not player FPL points',
                 assistant_ratio_provider=round(ass/goal,4) if goal>0 else None,
                 scoreline_warning='Source player assists are not guaranteed to use FPL assist rules',
                 train='GW6-21 (gamma only)',test='GW22-38 untouched by gamma selection',
                 method='lagged player rates shrunk to position prior (tau 900 minutes); oracle actual target minutes',
                 comparison='gamma=1.0 baseline vs development-selected concentration power',
                 goal=reports['goal'],assist=reports['assist'],
                 model_promotion=False)
    print('SHARE_TEST_COMPLETE',json.dumps({k:v for k,v in results.items() if k not in ['goal','assist']}))
    out=ROOT/'work/goal-assist-share-historical.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n')

if __name__=='__main__':main()
