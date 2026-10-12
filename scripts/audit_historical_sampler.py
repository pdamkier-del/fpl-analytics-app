#!/usr/bin/env python3
"""Paired PM component replay; reused GW22–38, never an independent TS test."""
import sys,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_vfinal_integrated import build_final_frame,make_vfinal_input,score
from fpl_v1_1_model.paired_joint import read_frozen_table
from fpl_v1_1_model.joint_simulator import simulate_many
from fpl_v1_1_model.experimental_mean_preserving_minutes import shadow_sampler
OUT=ROOT/'analysis/results/full-model-audit-20261012'
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 f=build_final_frame();truth=read_frozen_table(ROOT/'analysis/results/deadline-joint-inputs-v1','targets');rows=[]
 for i,fx in enumerate(sorted(f.fixture_uuid.unique())):
  g=f[f.fixture_uuid.eq(fx)];inp,_=make_vfinal_input(g)
  original=simulate_many(inp,n=400,seed=39092501+i)
  with shadow_sampler():candidate=simulate_many(inp,n=400,seed=39092501+i)
  for r in g.itertuples():
   pid=str(r.player_uuid);rows.append(dict(fixture_uuid=fx,player_uuid=pid,gw=int(r.gw),pos=r.pos,original=original[pid]['xPts'],candidate=candidate[pid]['xPts'],minutes_original=original[pid]['expected_minutes'],minutes_candidate=candidate[pid]['expected_minutes']))
  if i%20==0:print('Completed fixtures',i,flush=True)
 p=pd.DataFrame(rows).merge(truth,on=['fixture_uuid','player_uuid'],validate='one_to_one')
 metrics={}
 for name,g in [('all',p),('GW22_30',p[p.gw.le(30)]),('GW31_38',p[p.gw.gt(30)])]:
  metrics[name]={'rows':len(g),'original':score(g.total_points,g.original),'candidate':score(g.total_points,g.candidate)}
 diff=(p.candidate-p.total_points).abs()-(p.original-p.total_points).abs()
 blocks=pd.DataFrame({'fixture':p.fixture_uuid,'diff':diff}).groupby('fixture').agg(total=('diff','sum'),n=('diff','size')).to_numpy()
 rng=np.random.default_rng(20261012);idx=rng.integers(len(blocks),size=(4000,len(blocks)));draw=blocks[idx].sum(axis=1);ci=np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist()
 report=dict(classification='REUSED_COMPONENT_DIAGNOSTIC_NOT_INDEPENDENT',season='2025-26',cohort='archived integrated vFinal GW22-38; not locked 2125 six-GW TS replay',draws=400,seed=39092501,fixtures=int(p.fixture_uuid.nunique()),metrics=metrics,paired_mae_delta=float(diff.mean()),fixture_block_bootstrap_95_ci=ci,promotion_allowed=False,locked_model_active=False)
 p.to_csv(OUT/'historical_sampler_predictions.csv.gz',index=False,compression='gzip');(OUT/'historical_sampler_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
