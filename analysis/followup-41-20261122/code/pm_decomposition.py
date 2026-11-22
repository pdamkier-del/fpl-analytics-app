"""Exact descriptive decomposition of existing forecast errors; no fitted correction."""
from pathlib import Path
import json,gzip
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[1];A=R.parent/'audits/2026-11-22';O=R/'results';O.mkdir(exist_ok=True)
d=pd.read_csv(A/'results/enriched-player-evaluation.csv');groups=['gw','fixture','team']
# Conditional-volume attribution uses the forecast's own shares and realized team totals.
# The allocation term includes minutes/role effects: this is not pure tactical ability.
rows=[];details=[]
for target in ['goals','assists']:
 mu=d.groupby(groups)['pred_'+target].transform('sum');n=d.groupby(groups)['actual_'+target].transform('sum');supported=mu>0
 p=d['pred_'+target];y=d['actual_'+target];s=np.where(supported,p/mu,0);volume=s*(mu-n);allocation=s*n-y;error=p-y
 assert np.allclose(error[supported],(volume+allocation)[supported])
 x=d[['gw','fixture','team','id','position']].copy();x['target']=target;x['supported']=supported;x['forecast']=p;x['actual']=y;x['share']=s;x['volume_error']=volume;x['allocation_error']=allocation;x['error']=error;details.append(x)
 for label,g in [('all',x),*[(f'GW{gw}',g)for gw,g in x.groupby('gw')]]:
  g=g[g.supported];oracle=g.forecast-g.volume_error
  rows.append({'target':target,'group':label,'rows':len(g),'mean_squared_error':float((g.error**2).mean()),'volume_mean_square':float((g.volume_error**2).mean()),'allocation_mean_square':float((g.allocation_error**2).mean()),'cross_term':float((2*g.volume_error*g.allocation_error).mean()),'actual_team_volume_oracle_mse':float(((oracle-g.actual)**2).mean()),'predicted':float(g.forecast.sum()),'actual':int(g.actual.sum()),'unsupported_rows':int((~x.supported).sum())})
# Three-stage assist identity links team goal production to assist eligibility and player allocation.
muG=d.groupby(groups).pred_goals.transform('sum');YG=d.groupby(groups).actual_goals.transform('sum');muA=d.groupby(groups).pred_assists.transform('sum');YA=d.groupby(groups).actual_assists.transform('sum');support=(muG>0)&(muA>0)
sh=np.where(muA>0,d.pred_assists/muA,0);rate=np.where(muG>0,muA/muG,0)
ass=d[['gw','fixture','team','id']].copy();ass['goal_volume']=sh*rate*(muG-YG);ass['assist_eligibility_rate']=sh*(rate*YG-YA);ass['player_allocation']=sh*YA-d.actual_assists;ass['error']=d.pred_assists-d.actual_assists;ass['supported']=support
assert np.allclose(ass.loc[support,'error'],ass.loc[support,['goal_volume','assist_eligibility_rate','player_allocation']].sum(axis=1))
ass.to_csv(O/'pm-assist-three-stage-rows.csv',index=False)
assist_stages={k:float(ass.loc[support,k].sum())for k in ['goal_volume','assist_eligibility_rate','player_allocation','error']};assist_stages['scope']='Exact conditional identity using credited team goals; FPL own-goal-assists and omitted forecast own-goal means limit an interpretation as a literal assist probability.'
parts=pd.concat(details,ignore_index=True);parts.to_csv(O/'pm-volume-allocation-rows.csv',index=False);pd.DataFrame(rows).to_csv(O/'pm-volume-allocation-summary.csv',index=False)
# CS-point errors: qualification (60+) versus clean sheet conditional on qualification.
cs=[];csbounds=[];identity=[]
for gw in [8,9,10]:
 load=lambda n:json.loads(gzip.decompress((A/'inputs/archive'/n).read_bytes()))
 f=load(f'gw{gw}-forecast.json.gz');actual={p['id']:p for p in load(f'gw{gw}-live.json.gz')['elements']};fixtures={p['id']:p for p in load('fixtures.json.gz')};by={}
 for p in f['players']:
  w=next(w for w in p['weeks']if w['gw']==gw);x=w['fixtures'][0];m=np.asarray(w['scenarios']['minutes']);q=float((m>=60).mean());factor=4 if p['position']in [1,2]else 1 if p['position']==3 else 0
  if factor:
   z=x['components']['cs_points']/factor;c=z/q if q else None;s=actual[p['id']]['stats'];obsq=int(s['minutes']>=60);explain=next(e for e in actual[p['id']]['explain']if str(e['fixture'])==x['fixture_uuid'].split('-')[-1]);obsz=sum(v['points']for v in explain['stats']if v['identifier']=='clean_sheets')/factor
   eligibility=factor*c*(q-obsq)if c is not None else None;conditional=factor*(c*obsq-obsz)if c is not None else None
   if c is not None:assert np.isclose(x['components']['cs_points']-factor*obsz,eligibility+conditional)
   cs.append({'gw':gw,'fixture':x['fixture_uuid'],'id':p['id'],'position':p['position'],'qualification_probability':q,'conditional_cs_probability':c,'predicted_points':factor*z,'actual_points':factor*obsz,'eligibility_error':eligibility,'conditional_cs_error':conditional,'supported':c is not None})
  if p['position']==1:by.setdefault((x['fixture_uuid'],p['team_id']),[]).append((p,m,x))
 for (fx,team),ks in by.items():
  m=np.array([k[1]for k in ks]);q=(m>=60).sum(axis=0);conserved=bool(np.all(m.sum(axis=0)==90)and np.all(q<=1));C=sum(k[2]['components']['cs_points']/4 for k in ks)
  if not conserved:csbounds.append({'gw':gw,'fixture':fx,'team':team,'identified':False,'reason':'Keeper coverage or joint-minute sum not conserved'});continue
  partial=float(np.any((m>=60)&(m<90),axis=0).mean());notfull=float((~np.any(m==90,axis=0)).mean());lo=max(0.,C-partial);hi=min(1.,C+notfull);game=fixtures[int(fx.split('-')[-1])];opgoals=game['team_a_score']if team==game['team_h']else game['team_h_score'];y=int(opgoals==0)
  csbounds.append({'gw':gw,'fixture':fx,'team':team,'identified':True,'reason':'bounds from conserved keeper minutes and clean-sheet points; exact only if bounds coincide','cs_probability_low':lo,'cs_probability_high':hi,'actual_team_cs':y,'brier_low':lo**2 if y==0 else(1-hi)**2,'brier_high':hi**2 if y==0 else(1-lo)**2,'width':hi-lo})
c=pd.DataFrame(cs);c.to_csv(O/'pm-clean-sheet-decomposition.csv',index=False);b=pd.DataFrame(csbounds);b.to_csv(O/'pm-team-cs-bounds.csv',index=False);v=b[b.identified];sup=c[c.supported]
# Distinguish chance production, observed shot quality and finishing realization.
production=d.groupby('gw').agg(predicted_goals=('pred_goals','sum'),shot_xg=('observed_shot_xg','sum'),goals=('actual_goals','sum'),predicted_assists=('pred_assists','sum'),shot_xa=('observed_shot_xa','sum'),fpl_assists=('actual_assists','sum'));production['forecast_minus_shot_xg']=production.predicted_goals-production.shot_xg;production['shot_xg_minus_goals']=production.shot_xg-production.goals;production.to_csv(O/'pm-team-production.csv')
out={'scope':'New error decomposition only, same previously seen GW8-10; no simulation or fitted coefficients','formula':'player error = forecast share*(forecast team total-actual team total) + (forecast share*actual team total-actual player event)','allocation_note':'Includes role/minute effects and outcome noise; not a causal or deployable correction','production_totals':{k:float(v)for k,v in production.sum().items()},'allocation':rows,'assist_three_stage':assist_stages,'clean_sheets':{'supported_player_rows':len(sup),'unsupported_player_rows':int((~c.supported).sum()),'qualification_error_sum':float(sup.eligibility_error.sum()),'conditional_cs_error_sum':float(sup.conditional_cs_error.sum()),'total_supported_error':float((sup.predicted_points-sup.actual_points).sum()),'team_rows_with_probability_bounds':len(v),'team_rows_excluded':int((~b.identified).sum()),'mean_team_cs_probability_bounds':[float(v.cs_probability_low.mean()),float(v.cs_probability_high.mean())],'observed_team_cs':float(v.actual_team_cs.mean()),'team_cs_brier_bounds':[float(v.brier_low.mean()),float(v.brier_high.mean())],'note':'Bounds depend on archived joint keeper sample conservation; no Poisson assumption is introduced'},'BPS_identifiability':'Only bonus means, not sampled background-BPS/DC covariance or event-level BPS, are archived in these public forecasts; direct BPS-mean forecast error is not identified. Rule oracle and known proxy/code gap reused from PR41.','production_changed':False}
(O/'pm-decomposition.json').write_text(json.dumps(out,indent=2,sort_keys=True));print(json.dumps({k:v for k,v in out.items()if k!='allocation'},indent=2))
