"""Refit existing shared allocation architecture on NP-only targets/features."""
import argparse,json,sqlite3,hashlib
from pathlib import Path
import numpy as np,pandas as pd
from scipy.optimize import minimize
from fpl_v1_1_model.experimental_penalty_neutral import PenaltyNeutralState
from fpl_v1_1_model.experimental_nonpenalty_allocation import recent_features,FEATURES
from fpl_v1_1_model.role_event_priors import QCOLS
from run_soft_role_performance_allocation import fit_allocator
ROOT=Path(__file__).resolve().parents[1]


def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 protocol=dict(training='2025/26 GW16-21, existing development window; no validation results used',event='verified FPL-scale npxG estimate, .79 per scored or missed penalty',features=FEATURES,allocation='existing shared fit_allocator, fixed L2=200; ordinary-goal head only',attack='refit half-life and shrinkage minutes using development NP-xG Poisson loss, bounded prior ranges; no player-specific parameters',validation='2025/26 GW22-38 primary reused diagnostic; 2024/25 GW22-38 conditional robustness, not independent chronological holdout',selection='One fixed candidate, no holdout tuning',promotion='hard structural separation and unchanged default production; overall xP MAE noninferiority <=.005, played <=.02 per season; report taker bias and all cohorts without hiding regressions')
 (a.out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
 with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True)as c:h=pd.read_sql_query("SELECT * FROM player_fixture_observations WHERE is_final=1 AND season='2025-26'",c)
 h['available_at']=pd.to_datetime(h.kickoff_at,utc=True)+pd.Timedelta(hours=3)
 src=pd.read_csv(ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz',low_memory=False)
 roles=src[['fixture_uuid','player_uuid','team_id','cutoff','max_history_known_at']+QCOLS]
 events=pd.read_csv(ROOT/'analysis/results/penalty-neutral-sources-20261023/verified-attempts.csv');events=events[events.season.eq('2025-26')][['season','fixture_uuid','player_uuid','attempts']]
 original=json.loads((ROOT/'analysis/results/joint-component-recovery-v1/player_attack_fit.json').read_text());state=PenaltyNeutralState(h,events,roles,original)
 rows=[];sequences=[]
 for gw in range(16,22):
  target=src[src.gw.eq(gw)].copy();cut=pd.Timestamp(target.cutoff.min());target=target.drop(columns=['minutes','xg'],errors='ignore');target=target.merge(state.neutral[['fixture_uuid','player_uuid','minutes','xg']],on=['fixture_uuid','player_uuid'],validate='one_to_one')
  _,rates=state.factors(target,cut,'2025-26');f=target.merge(rates,on=['fixture_uuid','player_uuid'],validate='one_to_one').merge(recent_features(state.neutral,target,cut),on=['fixture_uuid','player_uuid'],validate='one_to_one');rows.append(f)
  past=state.neutral[pd.to_datetime(state.neutral.available_at,utc=True)<cut].sort_values(['kickoff_at','fixture_uuid','team_id','player_uuid']);by={pid:g for pid,g in past.groupby('player_uuid')}
  for r in f.itertuples():
   g=by.get(r.player_uuid,past.iloc[:0]);sequences.append((g.xg.to_numpy(float),g.minutes.to_numpy(float),float(r.nonpenalty_role_prior90),float(r.minutes),float(r.xg)))
 def loss(theta):
  half,tau=np.exp(theta);total=0.
  for x,m,prior,minutes,y in sequences:
   w=2**(-np.arange(len(x)-1,-1,-1)/half);rate=90*(w@x+tau*prior/90)/(w@m+tau);mu=max(1e-12,rate*minutes/90);total+=mu-y*np.log(mu)
  return total/len(sequences)
 old=original['goal'];fit=minimize(loss,np.log([old['recency_half_life'],old['current_season_position_prior_minutes_tau']]),method='L-BFGS-B',bounds=[(np.log(2.),np.log(100.)),(np.log(30.),np.log(3000.))])
 if not fit.success:raise ValueError(fit.message)
 attack=json.loads(json.dumps(original));attack['goal']['recency_half_life'],attack['goal']['current_season_position_prior_minutes_tau']=map(float,np.exp(fit.x));attack={'goal':{k:v for k,v in attack['goal'].items()if k in ['recency_half_life','current_season_position_prior_minutes_tau']}}
 f=pd.concat(rows,ignore_index=True);_,model=fit_allocator(f,'xg','nonpenalty_role_prior90',f[FEATURES],200.,np.ones(len(f),bool))
 receipt=dict(version='nonpenalty-goal-head-v1',attack=attack,allocation=model,training_rows=len(f),training_min_gw=16,training_max_gw=21,original_attack_loss=float(loss(np.log([old['recency_half_life'],old['current_season_position_prior_minutes_tau']]))),fitted_attack_loss=float(fit.fun),production_changed=False)
 (a.out/'model.json').write_text(json.dumps(receipt,indent=2)+'\n');f.to_csv(a.out/'training.csv.gz',index=False);print('Fitted clean NP head',receipt['training_rows'],attack['goal'],flush=True)
if __name__=='__main__':main()
