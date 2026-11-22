"""Out-of-sample opponent/home-adjusted xG dynamics. Exploratory, not production."""
import io,json,urllib.request
from collections import defaultdict
import numpy as np,pandas as pd
URL="https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/2025-26/gws/merged_gw.csv"
def main():
 with urllib.request.urlopen(URL,timeout=90) as r: f=pd.read_csv(io.BytesIO(r.read()),low_memory=False)
 required={'fixture','team','opponent_team','was_home','expected_goals','minutes','element','kickoff_time'}
 assert required<=set(f)
 f['expected_goals']=pd.to_numeric(f.expected_goals,errors='coerce');f['minutes']=pd.to_numeric(f.minutes,errors='coerce')
 f=f[f.minutes.gt(0)].dropna(subset=['fixture','team','opponent_team','kickoff_time'])
 g=f.groupby(['fixture','team','opponent_team','was_home','kickoff_time'],as_index=False).agg(xg=('expected_goals','sum'),n=('element','nunique'),valid=('expected_goals','count'))
 g=g[(g.n>=11)&(g.n==g.valid)].copy();g['kickoff_time']=pd.to_datetime(g.kickoff_time,utc=True)
 g=g.sort_values(['kickoff_time','fixture','team'])
 assert len(g)>=400
 times=sorted(g.kickoff_time.unique());cutoff=times[int(len(times)*.65)]
 # Independent match-clock updates: predictions for same kickoff use strictly earlier fixtures.
 histories=defaultdict(list);rows=[]
 for when,batch in g.groupby('kickoff_time',sort=True):
  predictions=[]
  fixture_teams={fid:[str(t) for t in group.team] for fid,group in batch.groupby('fixture') if len(group)==2}
  for x in batch.itertuples(index=False):
   t=str(x.team);other=fixture_teams.get(x.fixture,[])
   if len(other)!=2 or t not in other:continue
   o=other[1] if other[0]==t else other[0]
   h=bool(x.was_home);own=histories[t];opp=histories[o]
   if len(own)<5 or len(opp)<5:continue
   def rate(series,alpha):
    z=np.array([v[0] for v in series]);return float(z.mean()) if alpha is None else float(np.average(z,weights=(1-alpha)**np.arange(len(z)-1,-1,-1)))
   def allow(series,alpha):
    z=np.array([v[1] for v in series]);return float(z.mean()) if alpha is None else float(np.average(z,weights=(1-alpha)**np.arange(len(z)-1,-1,-1)))
   # Multiplicative opponent adjustment with regularization towards league mean.
   # Fixed constants chosen BEFORE holdout, no future information used.
   def estimate(alpha):
    attack=rate(own,alpha);defence=allow(opp,alpha)
    return max(.01,attack)*max(.2,defence)/1.5
   hist=estimate(None);fixed=estimate(.15)
   volatility=float(np.std([v[0] for v in own[-5:]],ddof=1))
   adaptive=estimate(float(np.clip(.10+.15*volatility,.1,.4)))
   predictions.append((when,t,o,float(x.xg),hist,fixed,adaptive,h))
  for x in batch.itertuples(index=False):
   histories[str(x.team)].append((float(x.xg),np.nan)) 
  # Populate actual xGA with opponent's complete same-fixture xG, only after batch forecasts.
  lookup={(x.fixture,str(x.team)):float(x.xg) for x in batch.itertuples(index=False)}
  for x in batch.itertuples(index=False):
   other=fixture_teams.get(x.fixture,[])
   opponent=(other[1] if other[0]==str(x.team) else other[0]) if len(other)==2 and str(x.team) in other else None
   opp=lookup.get((x.fixture,opponent))
   if opp is not None: histories[str(x.team)][-1]=(float(x.xg),opp)
   else:histories[str(x.team)].pop() # missing opposing team: exclude for consistent xGA
  if when>=cutoff:rows.extend(predictions)
 assert len(rows)>=100
 a=np.array([[x[3],x[4],x[5],x[6]] for x in rows])
 metrics=lambda q:{'rmse':round(float(np.sqrt(np.mean((q-a[:,0])**2))),6),'mae':round(float(np.mean(abs(q-a[:,0]))),6)}
 res={'source':URL,'complete_team_match_rows':len(g),'holdout':len(rows),'cutoff':str(cutoff),'methods':{'historical_attack_defence':metrics(a[:,1]),'fixed_decay_attack_defence':metrics(a[:,2]),'adaptive_decay_attack_defence':metrics(a[:,3])},'warnings':['No home advantage adjustment yet; keep home as diagnostic','Dataset is one season, not the locked production model','League mean 1.5 is a predeclared provisional scale; predictive comparison is exploratory']}
 print(json.dumps(res,indent=2));open('team-xg-opponent-results.json','w').write(json.dumps(res,indent=2))
if __name__=='__main__':main()
