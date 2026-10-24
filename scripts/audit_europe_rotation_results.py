"""Independent metric/source audit of the offline European rotation replay."""
import gzip,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/europe-rotation-20261022'
KEY=['season','fixture_uuid','player_uuid']


def metric(z):
 return dict(rows=len(z),start_brier=float(((z.p-z.y)**2).mean()),minute_mae=float(abs(z.x-z.minutes).mean()),minute_bias=float((z.x-z.minutes).mean()))if len(z)else dict(rows=0)


def run():
 manifest=json.loads((OUT/'source-manifest.json').read_text())
 for name,digest in manifest['inputs'].items():
  assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
 assert hashlib.sha256((ROOT/'scripts/research_europe_rotation.py').read_bytes()).hexdigest()==manifest['code_sha256']
 p=ROOT/'analysis/results/mm-match-importance-20261016';m=json.loads((p/'rotation_content_manifest.json').read_text());name='individual_recorded_workload.csv.gz';b=gzip.decompress((p/name).read_bytes());assert len(b)==m[name]['content_bytes']and hashlib.sha256(b).hexdigest()==m[name]['content_sha256']
 mm=pd.read_csv(OUT/'mm-predictions.csv.gz',float_precision='round_trip');pm=pd.read_csv(OUT/'pm-predictions.csv.gz',float_precision='round_trip')
 logs=json.loads((OUT/'fit-log.json').read_text())
 for r in logs:
  if r['last_label_known_at']:assert pd.Timestamp(r['last_label_known_at'])<pd.Timestamp(r['cutoff'])
 clocks=pd.to_datetime(mm.europe_max_known_at,utc=True,format='mixed');cuts=pd.to_datetime(mm.cutoff,utc=True,format='mixed');assert (clocks.isna()|clocks.lt(cuts)).all()
 assert not mm.duplicated(KEY+['arm']).any()and not pm.duplicated(KEY+['arm']).any()
 assert np.allclose(mm.p*mm.s+(1-mm.p)*mm.q*mm.c,mm.x,rtol=0,atol=1e-7)
 assert np.allclose(mm.groupby(['season','fixture_uuid','team_id','arm']).p.sum(),11,rtol=0,atol=1e-6)
 hard=mm.news_eligible&mm.news_state.isin(['OUT','SUSPENDED']);assert mm.loc[hard,['p','q','x']].eq(0).all().all()
 flags=mm[mm.arm.eq('baseline')][KEY+['pos']];pm=pm.merge(flags,on=KEY,validate='many_to_one')
 sub={};uncertainty={}
 for season in ['2024-25','2025-26']:
  sub[season]={}
  for arm in ['baseline','candidate']:
   z=mm[mm.season.eq(season)&mm.arm.eq(arm)&mm.role_recovery_case&~mm.pos.isin(['GK','GKP'])]
   points=pm[pm.season.eq(season)&pm.arm.eq(arm)&pm.role_recovery_case&~pm.pos.isin(['GK','GKP'])];e=points.xp-points.total_points
   sub[season][arm]=dict(mm=metric(z),pm=dict(rows=len(points),xp_mae=float(abs(e).mean())if len(points)else None,xp_bias=float(e.mean())if len(points)else None))
  b=pm[pm.season.eq(season)&pm.arm.eq('baseline')];c=pm[pm.season.eq(season)&pm.arm.eq('candidate')];pair=b.merge(c,on=KEY,validate='one_to_one',suffixes=('_b','_c'))
  assert np.array_equal(pair.total_points_b,pair.total_points_c)
  pair['delta']=abs(pair.xp_c-pair.total_points_c)-abs(pair.xp_b-pair.total_points_b)
  group=pair.groupby('fixture_uuid').delta.agg(['sum','count']);rng=np.random.default_rng(20261022);values=[]
  for _ in range(2000):
   ix=rng.integers(0,len(group),len(group));values.append(float(group['sum'].to_numpy()[ix].sum()/group['count'].to_numpy()[ix].sum()))
  uncertainty[season]=dict(xp_mae_delta=float(pair.delta.mean()),fixture_paired_CI95=np.quantile(values,[.025,.975]).tolist())
 report=dict(classification='RESEARCH_COMPLETE_CANDIDATE_NOT_PROMOTED',source_hashes_verified=True,workload_content_verified=True,all_fit_labels_prior_to_cutoff=True,all_context_clocks_prior_to_cutoff=True,MM_identity_and_exact11_pass=True,hard_absences_preserved=True,outfield_role_recovery=sub,point_uncertainty=uncertainty,promotion_allowed=False,reasons=['Intended role-recovery subgroup worsens in 2024-25.','Only 11 eligible outfield recovery rows in 2025-26; incomplete European data.','Actual historical publication/ingestion timing and complete pre-cutoff future European fixture schedules are not certified.','Reused development/research periods are not pristine independent holdouts.'],interpretation='Small aggregate predictive improvements do not establish a general rule that a European start should erase a prior PL bench signal. No conclusion that European context is irrelevant.',production_changed=False,preview_changed=False)
 (OUT/'decision.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':run()
