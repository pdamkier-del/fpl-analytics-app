#!/usr/bin/env python3
"""Test whether archived 2025/26 PL FotMob match events can be retrieved
and reconciled to provider's archived final scores, before any statistical
game-state minute duration analysis. Read-only.
"""
import json,requests,pandas as pd
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'data_v1_1/raw/all-competitions-2025-26/GW22/matches.csv'
m=pd.read_csv(p)
m=m[m.match_id.astype(str).str.contains('-prem-')].head(5)
url='https://www.fotmob.com/api/data/matchDetails'
session=requests.Session()
session.headers.update({'User-Agent':'Mozilla/5.0 (compatible; FPL analytics backtest/1.0)', 'Accept':'application/json'})
for r in m.itertuples(index=False):
 try:
    x=session.get(url,params={'matchId':int(r.fotmob_id)},timeout=18)
    print('GAME_STATE_SOURCE_HTTP',json.dumps(dict(id=int(r.fotmob_id),status=x.status_code,bytes=len(x.content))),flush=True)
    if x.status_code!=200:print('SOURCE_ERROR',x.text[:280],flush=True);continue
    z=x.json();facts=z.get('content',{}).get('matchFacts',{})
    events=facts.get('events',{}).get('events',[])
    goals=[{k:e.get(k) for k in ['type','time','timeStr','isHome','homeScore','awayScore','ownGoal','isPenaltyShootoutEvent']}
           for e in events if str(e.get('type','')).lower() in ('goal','owngoal')]
    print('GAME_STATE_SOURCE_MATCH',json.dumps(dict(id=int(r.fotmob_id),
       general={k:z.get('general',{}).get(k) for k in ['finished','matchName']},
       full_score=[r.home_score,r.away_score],
       count_events=len(events),types=sorted(set(str(e.get('type')) for e in events)),
       goal_examples=goals,score_at_finish=z.get('header',{}).get('status',{}).get('scoreStr')),ensure_ascii=False),flush=True)
 except Exception as exc:
    print('GAME_STATE_SOURCE_FETCH_ERROR',json.dumps(dict(id=int(r.fotmob_id),error=str(exc)[:350])),flush=True)
