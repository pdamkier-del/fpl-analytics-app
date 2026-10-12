#!/usr/bin/env python3
"""Repeated seeds quantify Monte Carlo noise, not future forecast accuracy."""
import sys,json
from pathlib import Path
import numpy as np,pandas as pd
from scipy.stats import t
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_live_vfinal_joint_simulation import simulate
OUT=ROOT/'analysis/results/full-model-audit-20261012'
def main():
 original=pd.read_csv(ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1/vfinal_live_full_simulator_input.csv.gz',low_memory=False);candidate=pd.read_csv(OUT/'duration_pm_shadow_inputs.csv.gz',low_memory=False)
 offset={fx:i for i,fx in enumerate(sorted(original.fixture_uuid.unique()))};focus=original[original.target_gw.eq(original.target_gw.min())&original.player.isin(['Haaland','Saka'])];fixtures=set(focus.fixture_uuid);original=original[original.fixture_uuid.isin(fixtures)];candidate=candidate[candidate.fixture_uuid.isin(fixtures)];rows=[]
 for rep in range(8):
  seed=93000000+rep*100000
  a,_=simulate(original,draws=400,seed=seed,fixture_seed_offsets=offset);b,_=simulate(candidate,draws=400,seed=seed,fixture_seed_offsets=offset)
  paired=a.merge(b,on=['fixture_uuid','player_uuid'],suffixes=('_original','_candidate'),validate='one_to_one').merge(focus[['fixture_uuid','player_uuid','player']],on=['fixture_uuid','player_uuid'],validate='one_to_one')
  for r in paired.itertuples():rows.append(dict(player=r.player,replicate=rep,xp_original=r.xpts_fixture_original,xp_candidate=r.xpts_fixture_candidate,minutes_original=r.expected_minutes_original,minutes_candidate=r.expected_minutes_candidate))
  print('Completed precision replicate',rep,flush=True)
 p=pd.DataFrame(rows);summary={}
 for name,g in p.groupby('player'):
  delta=g.xp_candidate-g.xp_original;se=delta.std(ddof=1)/np.sqrt(len(g));margin=t.ppf(.975,len(g)-1)*se
  summary[name]=dict(xp_original_mean=float(g.xp_original.mean()),xp_candidate_mean=float(g.xp_candidate.mean()),paired_xp_delta=float(delta.mean()),monte_carlo_delta_95_ci=[float(delta.mean()-margin),float(delta.mean()+margin)],minutes_original_mean=float(g.minutes_original.mean()),minutes_candidate_mean=float(g.minutes_candidate.mean()))
 report=dict(classification='MONTE_CARLO_PRECISION_NOT_ACCURACY_BACKTEST',replicates=8,draws_per_replicate=400,seed_base=93000000,seed_stride=100000,focus=summary,promotion_allowed=False)
 p.to_csv(OUT/'duration_pm_precision.csv',index=False);(OUT/'duration_pm_precision_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
