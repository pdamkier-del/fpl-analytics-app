#!/usr/bin/env python3
"""Exploratory, strictly walk-forward team finishing calibration; locked model unchanged."""
from pathlib import Path
import pandas as pd,numpy as np,json
B=Path('data_v1_1/derived/live_locked_inputs/2026-27-v1')
h=pd.read_csv(B/'observed_team_xg_history.csv.gz')
ph=pd.read_csv(B/'player_fixture_observations.csv.gz',low_memory=False)
goals=ph.groupby(['fixture_uuid','team_id'],as_index=False).goals.sum()
h=h.merge(goals,on=['fixture_uuid','team_id'],validate='one_to_one')
h=h.sort_values(['gw','fixture_uuid','team_id']).reset_index(drop=True)
assert (h.gw<7).all() and h.fixture_uuid.nunique()>=20
results=[]
for gw in sorted(h.gw.unique()):
 if gw<3:continue
 past=h[h.gw<gw];future=h[h.gw==gw]
 avg=float(past.xg.mean())
 attack=past.groupby('team_id').xg.agg(['sum','count'])
 defen=past.groupby('opponent_team_id').xg.agg(['sum','count'])
 for r in future.itertuples(index=False):
  if r.team_id not in attack.index or r.opponent_team_id not in defen.index:continue
  # shrink attacks and defences toward the past-only league xG; no test fixture leakage.
  ar=(attack.loc[r.team_id,'sum']+3*avg)/(attack.loc[r.team_id,'count']+3)
  dr=(defen.loc[r.opponent_team_id,'sum']+3*avg)/(defen.loc[r.opponent_team_id,'count']+3)
  base=float(ar*dr/avg)
  for tau in [float('inf'),2,5,10,20,50]:
   prev=past[past.team_id==r.team_id]
   # Bayesian-style shrinkage: team goals vs xG, not raw finite-sample ratio.
   fac=1. if np.isinf(tau) else (float(prev.goals.sum())+tau)/(float(prev.xg.sum())+tau)
   pred=max(.05,base*fac);actual=float(r.goals)
   results.append(dict(gw=int(gw),team=int(r.team_id),tau='none' if np.isinf(tau) else str(tau),pred=pred,actual=actual,abs_error=abs(pred-actual),poisson_deviance=2*(actual*np.log(actual/pred)-(actual-pred)) if actual>0 else 2*pred))
out=pd.DataFrame(results)
summary=out.groupby('tau',sort=False).agg(n=('actual','size'),mae=('abs_error','mean'),poisson_deviance=('poisson_deviance','mean'),mean_pred=('pred','mean'),mean_actual=('actual','mean')).reset_index()
print('FINISH_WALK_FORWARD',summary.round(5).to_json(orient='records'))
print('FINISH_EVAL_WINDOW',sorted(out.gw.unique().tolist()),'TEAMS',int(out.team.nunique()),'ROWS_PER_VARIANT',int(summary.n.iloc[0]))
baseline=summary[summary.tau.eq('none')].iloc[0]
best=summary.sort_values('poisson_deviance').iloc[0]
print('FINISH_RESULT',json.dumps(dict(best_tau=best.tau,baseline_deviance=round(float(baseline.poisson_deviance),5),best_deviance=round(float(best.poisson_deviance),5),delta_deviance=round(float(best.poisson_deviance-baseline.poisson_deviance),5),baseline_mae=round(float(baseline.mae),5),best_mae=round(float(best.mae),5),interpretation='Exploratory proxy baseline, NOT frozen PM head-to-head or independent season holdout')))
