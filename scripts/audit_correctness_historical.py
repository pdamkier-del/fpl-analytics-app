#!/usr/bin/env python3
"""Two-season simulator-correctness ablation on fixed cutoff-generated inputs."""
import argparse,gzip,json,sqlite3,sys,hashlib
from pathlib import Path
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.joint_simulator import MatchSimInput,PlayerSimInput,simulate_many
from fpl_v1_1_model.negative_events import DisciplineProbabilities
from fpl_v1_1_model.experimental_correctness_simulator import shadow_simulator,start_marginals,simulate_match
from fpl_v1_1_model.experimental_mean_preserving_minutes import clipped_rounded_mean
MODES={'own_goals':dict(own_goals=True,joint_xi=False),'joint_xi':dict(own_goals=False,joint_xi=True),'combined':dict(own_goals=True,joint_xi=True)}
def decode(data):
 ps=[]
 for p in data.pop('players'):
  p['discipline']=DisciplineProbabilities(**p['discipline'])
  if p.get('save_bucket_tilts') is not None:p['save_bucket_tilts']=tuple(p['save_bucket_tilts'])
  ps.append(PlayerSimInput(**p))
 return MatchSimInput(players=tuple(ps),**data)
def metric(g):
 err=g.xp-g.total_points
 return dict(rows=len(g),mae=float(abs(err).mean()),rmse=float(np.sqrt((err**2).mean())),minute_mae=float(abs(g.sim_minutes-g.minutes).mean()))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--season',required=True);ap.add_argument('--db',required=True);ap.add_argument('--out',required=True);a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(f'file:{Path(a.db).resolve()}?mode=ro',uri=True) as c:
  truth=pd.read_sql_query('SELECT fixture_uuid,player_uuid,total_points,minutes,started FROM player_fixture_observations WHERE season=? AND is_final=1',c,params=[a.season]);fx=pd.read_sql_query('SELECT fixture_uuid,home_team_id,away_team_id FROM fixtures WHERE season=?',c,params=[a.season])
 if fx.duplicated(['home_team_id','away_team_id']).any():raise ValueError('Nonunique fixture sides')
 mapping={(int(r.home_team_id),int(r.away_team_id)):str(r.fixture_uuid) for r in fx.itertuples()};rows=[];diags=[];fail=[]
 with gzip.open(a.inputs,'rt') as z:
  for i,line in enumerate(z):
   r=json.loads(line);inp=decode(r['input']);fid=mapping[(r['home'],r['away'])];marginal,diag=start_marginals(inp);diags.append(dict(fixture=fid,gw=r['origin'],teams=diag))
   values={mode:{} for mode in MODES}
   rngtrace=np.random.default_rng(r['seed']+1000000);capped=0;rejected=0
   for _ in range(100):
    trace={};simulate_match(inp,rngtrace,own_goals=False,trace=trace);capped+=trace['cameos_capped'];rejected+=trace['cameos_rejected']
   diags[-1].update(mean_cameos_capped_per_draw=capped/100,mean_cameos_rejected_per_draw=rejected/100)
   for mode,flags in MODES.items():
    try:
     with shadow_simulator(**flags):values[mode]=simulate_many(inp,n=400,seed=r['seed'])
    except ValueError as e:
     fail.append(dict(fixture=fid,gw=r['origin'],mode=mode,error=str(e)))
   for p in inp.players:
    if p.player_id not in r['reference']:continue
    rows.append(dict(fixture_uuid=fid,player_uuid=p.player_id,gw=r['origin'],pos=p.position,mode='original',xp=r['reference'][p.player_id],start_probability=p.p_start,sim_minutes=p.p_start*clipped_rounded_mean(p.start_minutes_mean,10.)+(1-p.p_start)*p.p_cameo_given_bench*clipped_rounded_mean(p.cameo_minutes_mean,7.,1,45)))
    for mode,sim in values.items():
     if p.player_id in sim:rows.append(dict(fixture_uuid=fid,player_uuid=p.player_id,gw=r['origin'],pos=p.position,mode=mode,xp=sim[p.player_id]['xPts'],start_probability=p.p_start if mode=='own_goals' else marginal[p.player_id],sim_minutes=sim[p.player_id]['expected_minutes']))
   if i%20==0:print(a.season,'completed fixtures',i,flush=True)
 p=pd.DataFrame(rows).merge(truth,on=['fixture_uuid','player_uuid'],validate='many_to_one',how='left',indicator=True)
 if not p._merge.eq('both').all():raise ValueError('Missing historical actuals; no zero imputation')
 p=p.drop(columns='_merge');p.to_csv(out/f'correctness_{a.season}_predictions.csv.gz',index=False,compression='gzip');metrics={};rng=np.random.default_rng(20261013)
 for mode,g in p.groupby('mode'):
  cohort={name:metric(sub) for name,sub in [('all',g),('played',g[g.minutes.gt(0)]),('late',g[g.gw.ge(22)])]}
  cohort['start_brier']=float(((g.start_probability-g.started)**2).mean());cohort['mean_start_probability']=float(g.start_probability.mean());cohort['actual_start_rate']=float(g.started.mean())
  if mode!='original':
   pair=g.merge(p[p['mode'].eq('original')][['fixture_uuid','player_uuid','xp']],on=['fixture_uuid','player_uuid'],suffixes=('','_original'),validate='one_to_one');d=abs(pair.xp-pair.total_points)-abs(pair.xp_original-pair.total_points)
   blocks=pd.DataFrame(dict(fixture=pair.fixture_uuid,delta=d)).groupby('fixture').delta.agg(['sum','size']).to_numpy();draw=blocks[rng.integers(len(blocks),size=(4000,len(blocks)))].sum(axis=1);cohort['paired_mae_delta']=float(d.mean());cohort['fixture_block_bootstrap_95_ci']=np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist()
  metrics[mode]=cohort
 report=dict(classification='CUTOFF_GENERATED_CORRECTNESS_ABLATION_NOT_INDEPENDENT_CERTIFICATION',season=a.season,fixtures=len(diags),draws=400,metrics=metrics,failed_fixture_modes=fail,marginal_diagnostics=diags,source_sha256=hashlib.sha256(Path(a.inputs).read_bytes()).hexdigest(),locked_model_active=False,promotion_allowed=False,limitations=['Frozen MM/component parameters, no player-specific tuning','2025/26 is a reused model-development period, with kickoff+3h proxy','2024/25 inherits existing conditional source/penalty/role/BPS proxies and kickoff+4h clock; not independent OOS','Original minute expectation computed analytically; candidate minute expectation estimated with 400 draws', 'Same seed per fixture and mode, but changed random draw ordering; bootstrap does not quantify all Monte Carlo uncertainty','No full-horizon TS promotion test; historical 2025 forecast horizon is incomplete'])
 (out/f'correctness_{a.season}_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(season=a.season,metrics=metrics,failures=fail),indent=2))
if __name__=='__main__':main()
