#!/usr/bin/env python3
"""Repeated-seed focus diagnostics, no player-specific mathematical changes."""
import sys,json
from pathlib import Path
from dataclasses import replace
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_vfinal_integrated import make_vfinal_input
from fpl_v1_1_model.joint_simulator import simulate_many
from fpl_v1_1_model.experimental_correctness_simulator import shadow_simulator,start_marginals
from audit_correctness_live import MODES
OUT=ROOT/'analysis/results/full-model-audit-20261012'
def main():
 f=pd.read_csv(ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1/vfinal_live_full_simulator_input.csv.gz',low_memory=False);f=f[f.target_gw.eq(7)];rows=[]
 for i,(fx,g) in enumerate(f.groupby('fixture_uuid',sort=True)):
  focus=g[g.player.isin(['Haaland','Saka'])]
  if focus.empty:continue
  inp,_=make_vfinal_input(g);inp=replace(inp,bps_rules='2026-27');marginal,_=start_marginals(inp)
  for rep in range(8):
   seed=93200000+i+rep*10000;result={'original':simulate_many(inp,n=400,seed=seed)}
   for mode,flags in MODES.items():
    with shadow_simulator(**flags):result[mode]=simulate_many(inp,n=400,seed=seed)
   for r in focus.itertuples():
    for mode,sim in result.items():rows.append(dict(player=r.player,mode=mode,repeat=rep,xp=sim[str(r.player_uuid)]['xPts'],minutes=sim[str(r.player_uuid)]['expected_minutes'],raw_p_start=next(p.p_start for p in inp.players if p.player_id==str(r.player_uuid)),candidate_p_start=marginal[str(r.player_uuid)]))
   print(fx,'repeat',rep,flush=True)
 p=pd.DataFrame(rows);summary=[]
 for (name,mode),g in p.groupby(['player','mode']):
  original=p[p.player.eq(name)&p['mode'].eq('original')].sort_values('repeat');g=g.sort_values('repeat');d=g.xp.to_numpy()-original.xp.to_numpy();se=float(d.std(ddof=1)/np.sqrt(8))
  summary.append(dict(player=name,mode=mode,mean_xp=float(g.xp.mean()),mean_minutes=float(g.minutes.mean()),paired_xp_delta=float(d.mean()),paired_seed_mean_95_ci=[float(d.mean()-2.364624*se),float(d.mean()+2.364624*se)],raw_p_start=float(g.raw_p_start.iloc[0]),candidate_p_start=float(g.candidate_p_start.iloc[0])))
 report=dict(classification='CURRENT_FORECAST_MONTE_CARLO_PRECISION_NOT_ACCURACY',cutoff=str(f.cutoff.iloc[0]),draws_per_repeat=400,repeats=8,summary=summary,locked_model_active=False,promotion_allowed=False,limitations=['Intervals describe simulation seed variation, not future point accuracy','Same source forecast and unchanged conditional starter/cameo distributions before timeline feasibility caps'])
 p.to_csv(OUT/'correctness_precision.csv',index=False);(OUT/'correctness_precision_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
