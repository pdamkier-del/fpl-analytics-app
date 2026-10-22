"""Frozen B role/NUM feature ablation; diagnostic only, no forecast publication.

Uses archived public inputs and checksum-verified source checkpoint in separate
folders. Upstream original MM, historical fitted samples, old role ledger, news,
fixtures and PM rates remain frozen. This tests B's PR4/PR9 feature path, not a
full upstream refit, causal accuracy, or an all-competition rotation candidate.
"""
import argparse,json,sys,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from audit_mm_components import prefix_features
from pr4_individual_mm import role_features,fit_role
from current_b_features import prior_features
from experimental_role_injury_mm import bounded_news
from mm_candidate_forecast import infer_B
from research_individual_mm_refinement import NUM
from mm_locked_bridge import attach_mm
from run_joint_gk_preview import run
from gk_joint_bridge import observations
from gk_solo_role import load_policy,mark_horizon_absences


def main():
 a=argparse.ArgumentParser();a.add_argument('--evidence',type=Path,required=True);a.add_argument('--source',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--repeats',type=int,default=8);args=a.parse_args()
 import build_current_b_inputs as b
 b.ROOT=args.source;b.BASE=args.source/'data_v1_1/derived/live_locked_inputs/2026-27-v1';b.WORK=args.source/'work/live-final-model'
 I=args.evidence/'work/current-B-inputs';prov=json.loads((I/'provenance.json').read_text());cut=pd.Timestamp(prov['data_at']);fx='live-2026-27-fpl-72'
 alltarget=pd.read_csv(I/'target.csv.gz',float_precision='round_trip');target=alltarget[alltarget.fixture_uuid.eq(fx)].copy().reset_index(drop=True)
 bootstrap=json.loads((I/'bootstrap.json').read_text());obs=b.current_observations(cut,bootstrap)
 hist=pd.read_csv(ROOT/'work/current-B-role-training/verified_observations.csv.gz',low_memory=False)
 for frame in [obs,hist]:
  for c in ['known','known_at']:frame[c]=pd.to_datetime(frame[c],utc=True,format='mixed')
 train=pd.read_csv(ROOT/'work/current-B-role-training/role_training.csv.gz',low_memory=False,float_precision='round_trip');train=train[pd.to_datetime(train.outcome_known_at,utc=True,format='mixed').lt(cut)]
 calibration=pd.read_csv(I/'history.csv.gz',low_memory=False,float_precision='round_trip')
 old=pd.read_csv(I/'role-ledger.csv.gz',low_memory=False,float_precision='round_trip');old=old[pd.to_datetime(old.cutoff,utc=True,format='mixed').lt(cut)].copy()
 prefix_cols=set(prefix_features(target[['player_uuid','team_id','cutoff','new_start_minutes']],obs))-{'player_uuid','team_id','cutoff','new_start_minutes'}
 rolecols=['role_logit','role_exposure','role_duration','role_cameo','role_cameo_minutes','role_band','role_max_known']
 def rebuild(history):
  frame=prefix_features(target.drop(columns=list(prefix_cols),errors='ignore'),history)
  frame,_=role_features(frame.drop(columns=rolecols,errors='ignore'),pd.concat([hist,history],ignore_index=True),42.)
  frame['p_role']=fit_role(train,frame,1.,'bands');frame['p']=frame.p_role
  # The archived normal-role memory and duration carry are intentionally fixed.
  frame['q']=frame.new_q_sub;frame['c']=frame.new_sub_minutes
  frame=bounded_news(frame,chance=True,project=True)
  assert not frame.projection_infeasible.any()
  return prior_features(frame,history,old)
 reconstructed=rebuild(obs)
 numeric_error={c:float(np.nanmax(abs(reconstructed[c].to_numpy(float)-target[c].to_numpy(float)))) for c in NUM}
 assert max(numeric_error.values())<1e-6,numeric_error
 print('Reconstructed archived B features; max error',max(numeric_error.values()),flush=True)
 arms={'baseline':target.copy()};removed={}
 ids={int(r.fpl_element):str(r.player_uuid) for r in target.itertuples()}
 latest={}
 for pid in [237,399]:
  rows=obs[obs.player_uuid.eq(ids[pid])].sort_values(['known_at','fixture_uuid']);latest[pid]=rows.iloc[-1]
 assert latest[237].fixture_uuid==latest[399].fixture_uuid
 for name,pids in [('omit_Ndiaye',[237]),('omit_Cherki',[399]),('omit_both',[237,399])]:
  mask=np.zeros(len(obs),bool)
  for pid in pids:mask|=obs.player_uuid.eq(ids[pid])&obs.fixture_uuid.eq(latest[pid].fixture_uuid)
  assert int(mask.sum())==len(pids)
  arms[name]=rebuild(obs.loc[~mask].copy());removed[name]=obs.loc[mask,['fixture_uuid','player_uuid','started','minutes','known_at']].astype(str).to_dict('records')
  print('Rebuilt',name,flush=True)
 single=target.copy()
 for pid in [237,399]:
  past=obs[obs.player_uuid.eq(ids[pid])&~obs.fixture_uuid.eq(latest[pid].fixture_uuid)].sort_values(['known_at','fixture_uuid'])
  single.loc[single.player_uuid.eq(ids[pid]),'last_started']=float(past.iloc[-1].started)
 arms['last_started_only']=single
 fullpm=pd.read_csv(I/'pm.csv.gz',low_memory=False,float_precision='round_trip');pm=fullpm[fullpm.fixture_uuid.eq(fx)].copy();offsets={x:i for i,x in enumerate(sorted(fullpm.fixture_uuid.unique()))}
 obs_gk=observations(ROOT);policy=load_policy(ROOT,calibration);catalogue={str(r.player_uuid):next(p for p in bootstrap['elements'] if p['id']==int(r.fpl_element)) for r in target.itertuples()}
 results={};seeds=[93000000+i*100000 for i in range(args.repeats)]
 baseline_pred,_=infer_B(calibration,target,prov)
 archived=json.loads((args.evidence/'work/joint-gk-current/forecast.json').read_text())
 for name,frame in arms.items():
  pred,_=infer_B(calibration,frame,prov);pred=mark_horizon_absences(pred,bootstrap);joined=attach_mm(pm,pred)
  # The bridge itself asserts byte-exact non-minute DataFrame equality.
  expected=pm.drop(columns=['v4_workload_start_p_start','v4_p_cameo_given_bench','v4_start_minutes_mean','v4_cameo_minutes_mean','v4_workload_start_xmins'])
  pd.testing.assert_frame_equal(expected,joined.drop(columns=['v4_workload_start_p_start','v4_p_cameo_given_bench','v4_start_minutes_mean','v4_cameo_minutes_mean','v4_workload_start_xmins']),check_exact=True)
  assert np.allclose(pred.groupby('team_id').p.sum(),11,atol=1e-8)
  runs=[];moments=None
  for seed in seeds:
   xp,moments,_,_=run(joined,pred,obs_gk,season='2026-27',draws=400,seed=seed,offsets=offsets,role_policy=policy,chain=True,catalogue=catalogue)
   runs.append(xp.set_index('player_uuid'))
  result={}
  for pid in [237,399]:
   uid=ids[pid];r=pred[pred.player_uuid.eq(uid)].iloc[0];m=moments[(fx,uid)];vals=[float(x.loc[uid,'xpts_fixture']) for x in runs]
   source=next(p for p in archived['players'] if p['id']==pid);sourceweek=next(w for w in source['weeks'] if w['gw']==8);saved=sourceweek['fixtures'][0]
   if name=='baseline':
    assert abs(float(r.p)-saved['p_start'])<1e-7,(pid,r.p,saved['p_start'])
    assert abs(m['x']-saved['xmins'])<1e-7
    assert vals[0]==saved['xpts'],(pid,vals[0],saved['xpts'])
   result[str(pid)]=dict(name=source['name'],p_start=float(r.p),xmins=float(m['x']),PM_E_minutes=float(m['x']),p_60_plus=float(m['p60']),p_90=float(m['p90']),xP_mean=float(np.mean(vals)),xP_per_seed=vals,xP_seed_standard_error=float(np.std(vals,ddof=1)/np.sqrt(len(vals))) if len(vals)>1 else None,PR4_role_p=float(frame.loc[frame.player_uuid.eq(uid),'p_role'].iloc[0]),last_started=float(frame.loc[frame.player_uuid.eq(uid),'last_started'].iloc[0]))
  results[name]=result;print(name,json.dumps(result),flush=True)
 for name,res in results.items():
  for pid,r in res.items():
   base=results['baseline'][pid];diff=np.asarray(r['xP_per_seed'])-np.asarray(base['xP_per_seed']);r['delta_start_percentage_points']=100*(r['p_start']-base['p_start']);r['delta_xmins']=r['xmins']-base['xmins'];r['delta_xP']=float(diff.mean());r['delta_xP_seed_standard_error']=float(diff.std(ddof=1)/np.sqrt(len(diff))) if len(diff)>1 else None
 report=dict(classification='FROZEN_B_FEATURE_ABLATION_NOT_MODEL_ACCURACY_VALIDATION',cutoff=prov['data_at'],fixture_uuid=fx,archived_forecast_sha256=archived['forecast_sha256'],target_sha256=hashlib.sha256((I/'target.csv.gz').read_bytes()).hexdigest(),repeats=args.repeats,draws_per_repeat=400,seeds=seeds,baseline_original_seed_exact=True,baseline_reconstruction_max_feature_errors=numeric_error,results=results,removed_observations=removed,scope=['Historical training labels and coefficients implied by the same fixed fit are unchanged across arms.','Only B PR4 prefix/role features and PR9 prior features are rebuilt after the observation is removed; original upstream MM, duration carry memory, news, PM offensive rates and opponents remain fixed.','Every ablation includes exact team projection; other player marginals may therefore move.','Removing an observation is not the same as declaring it tactical rest. No CL-informed rotation candidate is implemented.','Paired seeds are not event-aligned draws; standard errors describe Monte Carlo repeat variation, not forecast accuracy.','Baseline reproduces the archived 22 October 08:16 input run, slightly later than the 07:40 PM inputs served publicly.'],production_changed=False,model_changed=False)
 args.out.mkdir(parents=True,exist_ok=True);(args.out/'controlled-replay.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
