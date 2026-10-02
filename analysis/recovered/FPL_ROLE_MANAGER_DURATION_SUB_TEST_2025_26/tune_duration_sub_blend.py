from pathlib import Path
import numpy as np,pandas as pd,json
ROOT=Path('/mnt/data/fpl_resume/role_cache')
d=pd.read_csv(ROOT/'substitution_hierarchy_predictions.csv')
actual=d.minutes.to_numpy(float); p=d.p_regime.to_numpy(float)
tune=((d.gw>=12)&(d.gw<=21)).to_numpy(); test=(d.gw>=22).to_numpy()
# components
sm0=d.start_minutes_mean.to_numpy(float); sm1=d.start_minutes_duration_v2.to_numpy(float)
cm0=d.cameo_minutes_mean.to_numpy(float); cm1=d.cameo_minutes_duration_v2.to_numpy(float)
pc0=d.p_cameo_given_bench.to_numpy(float); pce=d.p_cameo_duration_v2.to_numpy(float); pch=d.p_cameo_hier.to_numpy(float)
# blend pc in two stages: empirical duration pc vs hierarchy pc. all choices made on tune only.
rows=[]; best=(1e9,None,None)
for a in np.linspace(0,1,11): # starter duration blend
 for b in np.linspace(0,1,11): # cameo duration blend
  for c in np.linspace(0,1,11): # baseline -> empirical cameo p
   for h in np.linspace(0,1,11): # then empirical -> hierarchy cameo p
    sm=(1-a)*sm0+a*sm1; cm=(1-b)*cm0+b*cm1
    pc_emp=(1-c)*pc0+c*pce; pc=(1-h)*pc_emp+h*pch
    xm=p*sm+(1-p)*pc*cm
    mae=float(np.mean(abs(xm[tune]-actual[tune]))); rmse=float(np.sqrt(np.mean((xm[tune]-actual[tune])**2)))
    rows.append((a,b,c,h,mae,rmse))
    if mae<best[0]:best=(mae,(a,b,c,h),xm)
resdf=pd.DataFrame(rows,columns=['start_blend','cameo_dur_blend','emp_cameo_p_blend','hier_cameo_p_blend','tune_mae','tune_rmse']).sort_values('tune_mae')
resdf.to_csv(ROOT/'duration_sub_blend_grid.csv',index=False)
_,pars,xm=best;a,b,c,h=pars
sm=(1-a)*sm0+a*sm1;cm=(1-b)*cm0+b*cm1;pc_emp=(1-c)*pc0+c*pce;pc=(1-h)*pc_emp+h*pch

def met(x,m):
 e=x[m]-actual[m];return {'mae':float(np.mean(abs(e))),'rmse':float(np.sqrt(np.mean(e*e))),'bias':float(np.mean(e))}
res={'selected':{'start_blend':a,'cameo_duration_blend':b,'empirical_cameo_prob_blend':c,'hierarchy_cameo_prob_blend':h},
     'tune':{'manager':met(d.xm_regime.to_numpy(),tune),'blend':met(xm,tune)},
     'test':{'base':met(d.xm_base.to_numpy(),test),'role':met(d.xm_role.to_numpy(),test),'manager':met(d.xm_regime.to_numpy(),test),'blend':met(xm,test)}}
for ref in ['base','role','manager']:
 res['test']['blend_vs_'+ref+'_pct']={k:100*(res['test']['blend'][k]/res['test'][ref][k]-1) for k in ['mae','rmse']}
d['p_cameo_blend']=pc;d['start_minutes_blend']=sm;d['cameo_minutes_blend']=cm;d['xm_duration_sub_blend']=xm
d.to_csv(ROOT/'duration_sub_blend_predictions.csv',index=False)
(ROOT/'duration_sub_blend_metrics.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps(res,indent=2))
print('\nTOP10')
print(resdf.head(10).to_string(index=False))
