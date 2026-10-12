#!/usr/bin/env python3
"""Independent historical team xG+actual-goals finishing correction evaluation.

ONLY Premier League fixture rows. Validation GW6-21; locked holdout GW22-38.
Does not modify or claim comparison against original frozen PM.
"""
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
FILES=sorted((ROOT/'data_v1_1/raw/all-competitions-2025-26').glob('GW*/matches.csv'))
frames=[]
for path in FILES:
    x=pd.read_csv(path,low_memory=False)
    x=x[x.match_id.astype(str).str.contains(r'^25-26-prem-',na=False)].copy()
    if not x.empty:frames.append(x)
assert len(FILES)==38 and frames
raw=pd.concat(frames,ignore_index=True)
raw=raw.drop_duplicates('match_id')
raw=raw[(raw.finished.astype(str).str.lower()=='true')].copy()
raw['gw']=pd.to_numeric(raw.gameweek,errors='coerce')
for c in ['home_expected_goals_xg','away_expected_goals_xg','home_score','away_score']:
    raw[c]=pd.to_numeric(raw[c],errors='coerce')
raw=raw.dropna(subset=['gw','home_team','away_team','home_expected_goals_xg','away_expected_goals_xg','home_score','away_score'])
sides=[]
for v in raw.itertuples(index=False):
    for team,opp,xg,goals,home in ((v.home_team,v.away_team,v.home_expected_goals_xg,v.home_score,True),(v.away_team,v.home_team,v.away_expected_goals_xg,v.away_score,False)):
        sides.append(dict(gw=int(v.gw),team=str(team),opponent=str(opp),xg=float(xg),goals=float(goals),home=home))
h=pd.DataFrame(sides)
assert h.gw.between(1,38).all() and h.team.nunique()==20
assert len(h)>=650,('Insufficient Premier League match-side coverage',len(h))
print('HISTORICAL_COVERAGE',dict(matches=len(h)//2,match_sides=len(h),teams=h.team.nunique(),gameweeks=h.gw.nunique()))
# Candidate shrinkage tau measured in expected goals; larger tau => more conservative.
taus=[None,2.,5.,10.,20.,50.,100.]
records=[]
for gw in range(6,39):
    past=h[h.gw<gw]
    fut=h[h.gw==gw]
    league=float(past.xg.mean())
    if len(past)<40 or league<=0:continue
    atk=past.groupby('team').xg.agg(['sum','count'])
    defense=past.groupby('opponent').xg.agg(['sum','count'])
    finishing=past.groupby('team')[['goals','xg']].sum()
    for r in fut.itertuples(index=False):
        if r.team not in atk.index or r.opponent not in defense.index:continue
        a=(atk.loc[r.team,'sum']+3*league)/(atk.loc[r.team,'count']+3)
        d=(defense.loc[r.opponent,'sum']+3*league)/(defense.loc[r.opponent,'count']+3)
        base=float(a*d/league)
        for tau in taus:
            fac=1 if tau is None else (finishing.loc[r.team,'goals']+tau)/(finishing.loc[r.team,'xg']+tau)
            pred=float(np.clip(base*fac,.05,6.))
            y=float(r.goals)
            dev=2*(y*np.log(y/pred)-(y-pred)) if y>0 else 2*pred
            records.append(dict(gw=gw,team=r.team,tau='none' if tau is None else str(int(tau)),actual=y,pred=pred,absolute_error=abs(pred-y),poisson_deviance=dev))
out=pd.DataFrame(records)
assert out.gw.max()==38 and out.gw.min()<=6
def scores(frame):
    return frame.groupby('tau').agg(n=('actual','size'),mae=('absolute_error','mean'),deviance=('poisson_deviance','mean'),predicted_goals=('pred','mean'),actual_goals=('actual','mean')).reset_index()
dev=scores(out[out.gw.between(6,21)])
hold=scores(out[out.gw.between(22,38)])
chosen=dev.sort_values(['deviance','mae'],kind='stable').iloc[0].tau
print('FINISH_DEVELOPMENT_GW6_21',dev.round(5).to_json(orient='records'))
print('FINISH_HOLDOUT_GW22_38',hold.round(5).to_json(orient='records'))
baseline=hold[hold.tau.eq('none')].iloc[0]
selected=hold[hold.tau.eq(chosen)].iloc[0]
print('FINISH_HOLDOUT_DECISION',dict(selected_tau=chosen,selected_deviance=round(float(selected.deviance),6),baseline_deviance=round(float(baseline.deviance),6),selected_mae=round(float(selected.mae),6),baseline_mae=round(float(baseline.mae),6),improves_both=bool(selected.deviance<baseline.deviance and selected.mae<baseline.mae),note='Independent proxy comparison, not frozen original PM'))
