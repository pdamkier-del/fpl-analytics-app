#!/usr/bin/env python3
"""General finishing shrinkage, chronological tau selection on 2024 early GWs.
Uses explicit kickoff+4h availability proxy, NOT recovered publication timestamps.
This is a transparent xG proxy comparison, not the frozen PM/TS benchmark.
"""
from pathlib import Path
import json,gzip,hashlib
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'analysis/results/full-model-audit-20261012'
TAUS=[None,2.,5.,10.,20.,50.,100.]
def load(season):
 sources=[];rows=[]
 if season=='2024-25':
  path=ROOT/'data_v1_1/derived/season_2024_25_v1/existing_core_team_fixture_observations.jsonl.gz';sources=[path]
  with gzip.open(path,'rt') as f:
   for line in f:
    r=json.loads(line)
    if r['xg'] is not None and r['gf'] is not None:rows.append(dict(fixture=r['fixture_uuid'],gw=int(r['gw']),kickoff=r['kickoff_at'],team=r['team_id'],opponent=r['opponent_team_id'],xg=r['xg'],goals=r['gf']))
  dp=ROOT/'data_v1_1/derived/season_2024_25_v1/deadlines.json'
 else:
  for path in sorted((ROOT/'data_v1_1/raw/all-competitions-2025-26').glob('GW*/matches.csv')):
   sources.append(path);x=pd.read_csv(path,low_memory=False)
   for r in x[x.match_id.astype(str).str.startswith('25-26-prem-')].drop_duplicates('match_id').itertuples():
    if str(r.finished).lower()!='true':continue
    for team,opp,xg,goals in [(r.home_team,r.away_team,r.home_expected_goals_xg,r.home_score),(r.away_team,r.home_team,r.away_expected_goals_xg,r.away_score)]:
     if pd.notna(xg) and pd.notna(goals):rows.append(dict(fixture=r.match_id,gw=int(r.gameweek),kickoff=r.kickoff_time,team=team,opponent=opp,xg=float(xg),goals=float(goals)))
  dp=ROOT/'data_v1_1/derived/team_news_audit/2025-26-v2/deadlines.json'
 sources.append(dp);deadlines={int(r['gw']):pd.Timestamp(r['cutoff']) for r in json.loads(dp.read_text())}
 h=pd.DataFrame(rows).drop_duplicates(['fixture','team']);h['available']=pd.to_datetime(h.kickoff,utc=True)+pd.Timedelta(hours=4)
 return h,deadlines,{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
def walk(h,deadlines):
 out=[]
 for gw,cutoff in sorted(deadlines.items()):
  if gw<6:continue
  past=h[h.available.lt(cutoff)];future=h[h.gw.eq(gw)]
  if len(past)<40:continue
  league=past.xg.mean();atk=past.groupby('team').xg.agg(['sum','count']);defense=past.groupby('opponent').xg.agg(['sum','count']);finish=past.groupby('team')[['goals','xg']].sum()
  assert past.available.max()<cutoff
  for r in future.itertuples():
   if r.team not in atk.index or r.opponent not in defense.index:continue
   base=((atk.loc[r.team,'sum']+3*league)/(atk.loc[r.team,'count']+3))*((defense.loc[r.opponent,'sum']+3*league)/(defense.loc[r.opponent,'count']+3))/league
   for tau in TAUS:
    factor=1. if tau is None else (finish.loc[r.team,'goals']+tau)/(finish.loc[r.team,'xg']+tau)
    pred=float(np.clip(base*factor,.05,6));y=float(r.goals);dev=2*(y*np.log(y/pred)-(y-pred)) if y else 2*pred
    out.append(dict(fixture=r.fixture,team=r.team,gw=gw,tau='none' if tau is None else str(int(tau)),actual=y,pred=pred,mae=abs(y-pred),deviance=dev,cutoff=str(cutoff),max_history_available=str(past.available.max())))
 return pd.DataFrame(out)
def metrics(p):return p.groupby('tau')[['mae','deviance']].mean().reset_index().to_dict('records')
def main():
 OUT.mkdir(parents=True,exist_ok=True);frames={};sources={};coverage={}
 for season in ['2024-25','2025-26']:
  h,d,s=load(season);sources.update(s);frames[season]=walk(h,d);coverage[season]=dict(match_sides=len(h),fixtures=int(h.fixture.nunique()),forecast_sides=int(len(frames[season])/len(TAUS)))
 dev=frames['2024-25'].query('gw<=21');selected=pd.DataFrame(metrics(dev)).sort_values(['deviance','mae']).iloc[0].tau
 results={};rng=np.random.default_rng(20261012)
 for name,p in [('2024-25_GW22-38',frames['2024-25'].query('gw>=22')),('2025-26_GW6-38',frames['2025-26'])]:
  pair=p[p.tau.eq('none')].merge(p[p.tau.eq(selected)],on=['fixture','team','gw'],suffixes=('_baseline','_candidate'),validate='one_to_one');pair['delta']=pair.mae_candidate-pair.mae_baseline
  blocks=pair.groupby('fixture').agg(total=('delta','sum'),n=('delta','size')).to_numpy();indices=rng.integers(len(blocks),size=(4000,len(blocks)));b=blocks[indices].sum(axis=1)
  results[name]=dict(scores=metrics(p),selected_tau=selected,paired_mae_delta=float(pair.delta.mean()),fixture_block_bootstrap_95_ci=np.quantile(b[:,0]/b[:,1],[.025,.975]).tolist())
 report=dict(classification='RETROSPECTIVE_CUTOFF_PROXY_COMPONENT_COMPARISON',availability='kickoff+4h documented proxy, not actual source publication',selection='2024-25 GW6-21 Poisson deviance then MAE',selected_tau=selected,coverage=coverage,results=results,sources=sources,promotion_allowed=False,limitations=['No full original PM or TS comparison','2024 xG is reconstructed from historical player observations; provider may differ from 2025','Historical publication clocks unavailable','2025 period has been used in previous model development; not a pristine independent whole-model holdout'])
 (OUT/'finishing_walkforward_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'}))
if __name__=='__main__':main()
