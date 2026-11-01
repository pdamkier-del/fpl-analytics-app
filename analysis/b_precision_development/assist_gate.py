"""Fixed-window paired acceptance, including rejected/uncertain candidates."""
import json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
OUT=Path('analysis/results/b-precision-development-20261101')
def interval(g,col,rng):
 b=g.groupby('fixture_uuid')[col].agg(['sum','size']).to_numpy();s=b[rng.integers(len(b),size=(4000,len(b)))].sum(axis=1);return np.quantile(s[:,0]/s[:,1],[.025,.975]).tolist()
def main():
 f=pd.read_csv(OUT/'baseline-assist-2000-predictions.csv.gz',low_memory=False);f=f[f.draws.eq(2000)];keys=['season','fixture_uuid','player_uuid'];b=f[f.arm.eq('baseline')];a=f[f.arm.eq('assist')];p=b.merge(a,on=keys,suffixes=('_b','_a'),validate='one_to_one');assert len(p)==len(b)==len(a)
 for c in ['analytic_minutes','analytic_start','analytic_p60','analytic_p90','minutes','started','goals']:assert np.allclose(p[c+'_a'],p[c+'_b'],atol=1e-12,rtol=0),c
 # Same events and assist-eligible candidate sets: total simulated assists fixed.
 team=p.groupby(['season','fixture_uuid','team_id_b'])[['assists_a','assists_b']].sum();assert np.max(abs(team.assists_a-team.assists_b))<1e-12
 p['delta_xp_abs']=abs(p.points_a-p.actual_points_a)-abs(p.points_b-p.actual_points_b);p['delta_assist_Brier']=(p.p_assist_a-p.actual_assists_a.ge(1))**2-(p.p_assist_b-p.actual_assists_b.ge(1))**2;rng=np.random.default_rng(20261101);summary=[];failures=[]
 for season,g in p.groupby('season'):
  groups=[('all',g),('played',g[g.actual_minutes_a.gt(0)])];groups.extend((pos,h)for pos,h in g.groupby('position_a'))
  for name,h in groups:
   row=dict(season=season,group=name,rows=len(h),fixtures=int(h.fixture_uuid.nunique()),expected_assists_before=float(h.assists_b.sum()),expected_assists_after=float(h.assists_a.sum()),actual_assists=int(h.actual_assists_a.sum()),assist_Brier_before=float(((h.p_assist_b-h.actual_assists_a.ge(1))**2).mean()),assist_Brier_after=float(((h.p_assist_a-h.actual_assists_a.ge(1))**2).mean()),xp_MAE_before=float(abs(h.points_b-h.actual_points_a).mean()),xp_MAE_after=float(abs(h.points_a-h.actual_points_a).mean()),xp_bias_before=float((h.points_b-h.actual_points_a).mean()),xp_bias_after=float((h.points_a-h.actual_points_a).mean()),xp_MAE_delta95=interval(h,'delta_xp_abs',rng),assist_Brier_delta95=interval(h,'delta_assist_Brier',rng));summary.append(row)
  by={r['group']:r for r in summary if r['season']==season};fw=by['FWD']
  if fw['assist_Brier_after']>=fw['assist_Brier_before']:failures.append(season+': FWD binary assist Brier did not improve')
  if abs(fw['xp_bias_after'])>=abs(fw['xp_bias_before']):failures.append(season+': absolute FWD xP bias did not improve')
  for name,limit in [('all',.005),('played',.02)]:
   if by[name]['xp_MAE_after']>by[name]['xp_MAE_before']+limit:failures.append(season+': '+name+' xP-MAE deterioration exceeds fixed limit')
 fw=p[p.position_a.eq('FWD')];pooled=interval(fw,'delta_assist_Brier',rng)
 if pooled[1]>0:failures.append('Pooled FWD paired fixture-bootstrap 95% interval includes no improvement; insufficient robust evidence for activation')
 result=dict(version='B-assist-calibration-gate-v1',accepted=not failures,failures=failures,policy_assist_sha256=hashlib.sha256(json.dumps(json.loads((OUT/'candidate-policy.json').read_text())['assist'],sort_keys=True).encode()).hexdigest(),same_MM_and_goal_samples=True,team_assist_budget_unchanged=True,paired_FWD_assist_Brier_delta95=pooled,test_windows=['2024-25 GW30-38','2025-26 GW22-38'],no_independent_accuracy_claim=True,metrics=summary)
 (OUT/'assist-decision.json').write_text(json.dumps(result,indent=2)+'\n');pd.DataFrame(summary).to_csv(OUT/'assist-gate-metrics.csv',index=False);print(json.dumps({k:v for k,v in result.items()if k!='metrics'},indent=2))
if __name__=='__main__':main()
