#!/usr/bin/env python3
"""Original versus opt-in simulator corrections at one frozen live cutoff."""
import sys,json
from pathlib import Path
from dataclasses import replace
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_vfinal_integrated import make_vfinal_input
from fpl_v1_1_model.joint_simulator import simulate_many
from fpl_v1_1_model.experimental_correctness_simulator import shadow_simulator,start_marginals,simulate_match
OUT=ROOT/'analysis/results/full-model-audit-20261012'
MODES={'own_goals':dict(own_goals=True,joint_xi=False),'joint_xi':dict(own_goals=False,joint_xi=True),'combined':dict(own_goals=True,joint_xi=True)}
def main():
 f=pd.read_csv(ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1/vfinal_live_full_simulator_input.csv.gz',low_memory=False)
 saved=pd.read_csv(ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1/live_vfinal_fixture_xp.csv.gz');rows=[];diags=[];failure=[]
 for i,(fx,g) in enumerate(f.groupby('fixture_uuid',sort=True)):
  inp,_=make_vfinal_input(g);inp=replace(inp,bps_rules='2026-27')
  marginal,d=start_marginals(inp);diags.append(dict(fixture=fx,teams=d))
  original=simulate_many(inp,n=400,seed=93000000+i)
  for pid,s in original.items():
   a=saved[saved.fixture_uuid.eq(fx)&saved.player_uuid.astype(str).eq(pid)]
   if len(a)!=1 or float(a.xpts_fixture.iloc[0])!=s['xPts']:raise ValueError('Original live reproduction differs')
  result={'original':original}
  for mode,flags in MODES.items():
   with shadow_simulator(**flags):result[mode]=simulate_many(inp,n=400,seed=93000000+i)
  for r in g.itertuples():
   pid=str(r.player_uuid)
   for mode,sim in result.items():rows.append(dict(fixture_uuid=fx,player_uuid=pid,player=r.player,gw=int(r.target_gw),team=int(r.team_id),mode=mode,xp=sim[pid]['xPts'],minutes=sim[pid]['expected_minutes'],sampled_start=sim[pid]['p_start'],input_start=next(p.p_start for p in inp.players if p.player_id==pid),projected_start=marginal[pid]))
  if i%10==0:print('Completed live fixtures',i,flush=True)
 p=pd.DataFrame(rows);OUT.mkdir(exist_ok=True,parents=True);p.to_csv(OUT/'correctness_live_predictions.csv.gz',index=False,compression='gzip')
 focus=p[p.player.isin(['Haaland','Saka'])].to_dict('records')
 che=f[f.team_id.eq(6)].groupby(['target_gw','fixture_uuid']).first().reset_index();chelsea=[dict(gw=int(r.target_gw),original_total_intensity=float(r.lambda_home_goals if r.home_team_id==6 else r.lambda_away_goals),candidate_total_intensity=float(r.lambda_home_goals if r.home_team_id==6 else r.lambda_away_goals)) for r in che.itertuples()]
 report=dict(classification='OPT_IN_CORRECTNESS_SHADOW_NO_PRODUCTION_PROMOTION',cutoff=str(f.cutoff.iloc[0]),draws=400,original_exact=True,focus=focus,chelsea_total_goal_intensity=chelsea,marginal_diagnostics=diags,limitations=['Conditional starter duration and locked MM unchanged','Cameo slot constraints can change exposure; all changes reported','FPL position groups are conservative proxies, not inferred tactical positions','One Monte Carlo seed per fixture; not accuracy validation'],locked_model_active=False)
 (OUT/'correctness_live_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(original_exact=True,focus=[r for r in focus if r['gw']==7],chelsea=chelsea),indent=2))
if __name__=='__main__':main()
