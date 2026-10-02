from pathlib import Path
import numpy as np, pandas as pd, json, itertools
from sklearn.metrics import brier_score_loss
ROOT=Path('/mnt/data/fpl_resume/role_cache')
d=pd.read_csv(ROOT/'manager_regime_v2_predictions.csv').sort_values(['team_id','player_uuid','gw','fixture_uuid']).reset_index(drop=True)
d.player_uuid=d.player_uuid.astype(str)
regime_starts={7:[1,22],14:[1,22],16:[1,4,9,27],18:[1,32],19:[1,6]}
def regstart(t,g):
 ss=regime_starts.get(int(t),[1]); return max(x for x in ss if x<=int(g))
d['regime_start']=[regstart(t,g) for t,g in zip(d.team_id,d.gw)]
N=len(d)
H=[3,6,10]
# stats arrays keyed half-life: weighted sum / weight for each component at each target
start_sum={h:np.zeros(N) for h in H}; start_w={h:np.zeros(N) for h in H}
cam_sum={h:np.zeros(N) for h in H}; cam_w={h:np.zeros(N) for h in H}
bench_play_sum={h:np.zeros(N) for h in H}; bench_w={h:np.zeros(N) for h in H}
for _,g in d.groupby(['team_id','player_uuid'],sort=False):
 idx=g.index.to_numpy(); gw=g.gw.to_numpy(float); rs=g.regime_start.to_numpy(int); y=g.y.to_numpy(int); mins=g.minutes.to_numpy(float)
 for j,ix in enumerate(idx):
  if j==0: continue
  valid=np.arange(j)[rs[:j]>=rs[j]]
  if not len(valid): continue
  ages=gw[j]-gw[valid]
  for h in H:
   w=2**(-ages/h)
   si=(y[valid]==1)
   if si.any():
    ww=w[si]; vv=mins[valid[si]]; start_sum[h][ix]=np.dot(ww,vv); start_w[h][ix]=ww.sum()
   bi=(y[valid]==0)
   if bi.any():
    ww=w[bi]; vv=mins[valid[bi]]; bench_w[h][ix]=ww.sum(); bench_play_sum[h][ix]=np.dot(ww,(vv>0).astype(float))
    ci=bi & (mins[valid]>0)
    if ci.any():
     wc=w[ci]; vc=mins[valid[ci]]; cam_w[h][ix]=wc.sum(); cam_sum[h][ix]=np.dot(wc,vc)

# candidate arrays
start_opts={}; cam_opts={}; p_opts={}
for h in H:
 for tau in [1,3,6,12]:
  w=start_w[h]; start_opts[(h,tau)]=np.clip((start_sum[h]+tau*d.start_minutes_mean.values)/(w+tau),1,90)
 for tau in [1,3,6]:
  w=cam_w[h]; cam_opts[(h,tau)]=np.clip((cam_sum[h]+tau*d.cameo_minutes_mean.values)/(w+tau),1,45)
 for tau in [2,5,10,20]:
  w=bench_w[h]; p_opts[(h,tau)]=np.clip((bench_play_sum[h]+tau*d.p_cameo_given_bench.values)/(w+tau),0,1)

tune=((d.gw>=12)&(d.gw<=21)).values; test=(d.gw>=22).values
pstart=d.p_regime.values; actual=d.minutes.values
rows=[]; best=(1e9,None,None)
for sk,sm in start_opts.items():
 for ck,cm in cam_opts.items():
  for pk,pc in p_opts.items():
   xm=pstart*sm+(1-pstart)*pc*cm
   mae=np.mean(np.abs(xm[tune]-actual[tune])); rmse=np.sqrt(np.mean((xm[tune]-actual[tune])**2))
   rows.append({'hs':sk[0],'tau_start':sk[1],'hc':ck[0],'tau_cameo':ck[1],'hp':pk[0],'tau_p_cameo':pk[1],'tune_mae':mae,'tune_rmse':rmse})
   if mae<best[0]: best=(mae,(sk,ck,pk),xm)
pd.DataFrame(rows).sort_values('tune_mae').to_csv(ROOT/'duration_substitution_tuning.csv',index=False)
_,keys,xm=best; sk,ck,pk=keys; sm=start_opts[sk]; cm=cam_opts[ck]; pc=p_opts[pk]
def met(x,m):
 e=x[m]-actual[m]; return {'mae':float(np.mean(abs(e))),'rmse':float(np.sqrt(np.mean(e*e))),'bias':float(np.mean(e))}
res={'selected':{'start_half_life':sk[0],'start_tau':sk[1],'cameo_minutes_half_life':ck[0],'cameo_minutes_tau':ck[1],'cameo_prob_half_life':pk[0],'cameo_prob_tau':pk[1]},
 'tune_gw12_21':{},'test_gw22_38':{}}
for name,x in [('base',d.xm_base.values),('role',d.xm_role.values),('manager_regime',d.xm_regime.values),('duration_sub',xm)]:
 res['tune_gw12_21'][name]=met(x,tune); res['test_gw22_38'][name]=met(x,test)
for ref in ['base','role','manager_regime']:
 res['test_gw22_38']['duration_vs_'+ref+'_pct']={k:100*(res['test_gw22_38']['duration_sub'][k]/res['test_gw22_38'][ref][k]-1) for k in ['mae','rmse']}
st=test&(d.y.values==1); cam=test&(d.y.values==0)&(actual>0); bench=test&(d.y.values==0)
res['component_test']={
 'starter_duration':{'n':int(st.sum()),'baseline_mae':float(np.mean(abs(d.start_minutes_mean.values[st]-actual[st]))),'new_mae':float(np.mean(abs(sm[st]-actual[st])))},
 'cameo_duration':{'n':int(cam.sum()),'baseline_mae':float(np.mean(abs(d.cameo_minutes_mean.values[cam]-actual[cam]))),'new_mae':float(np.mean(abs(cm[cam]-actual[cam])))},
 'cameo_probability':{'n':int(bench.sum()),'actual_rate':float((actual[bench]>0).mean()),'baseline_brier':float(brier_score_loss((actual[bench]>0).astype(int),d.p_cameo_given_bench.values[bench])),'new_brier':float(brier_score_loss((actual[bench]>0).astype(int),pc[bench]))}
}
d['start_minutes_duration_v2']=sm; d['cameo_minutes_duration_v2']=cm; d['p_cameo_duration_v2']=pc; d['xm_duration_v2']=xm
d.to_csv(ROOT/'duration_substitution_predictions.csv',index=False)
(ROOT/'duration_substitution_metrics.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps(res,indent=2))
