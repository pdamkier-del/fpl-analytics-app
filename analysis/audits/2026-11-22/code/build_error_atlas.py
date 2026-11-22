"""Descriptive disaggregation of archived forecasts. No fitting, inferred injury dates or invented cup clocks."""
from pathlib import Path
import json,gzip
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[1];O=R/'results';d=pd.read_csv(O/'player-evaluation.csv');P={1:10,2:6,3:5,4:4};meta=[];teams=[]
def load(n):return json.loads(gzip.decompress((R/'inputs/archive'/n).with_suffix('.json.gz').read_bytes()))
fixtures={f['id']:f for f in load('fixtures.json')};rng=np.random.default_rng(20261122)
for gw in (8,9,10):
 f=load(f'gw{gw}-forecast.json');mm=load(f'gw{gw}-mm.json');m={(p['fixture_id'],p['player_id']):p for p in mm['players']};live={p['id']:p for p in load(f'gw{gw}-live.json')['elements']}
 for p in f['players']:
  w=next(w for w in p['weeks'] if w['gw']==gw);x=w['fixtures'][0];r=m[x['fixture_uuid'],p['player_uuid']];a=live[p['id']]['stats'];meta.append({'gw':gw,'id':p['id'],'team':p['team_id'],'club':p['team'],'price_tenths':p['price_tenths'],'normal_role':r.get('normal_role','unavailable'),'availability':r.get('availability','unavailable'),'pred_goals':x['components']['goal_points']/P[p['position']],'actual_goals':a['goals_scored'],'pred_assists':x['components']['assist_points']/3,'actual_assists':a['assists'],'observed_shot_xg':float(a['expected_goals']),'observed_shot_xa':float(a['expected_assists']),'penalty_taker_probability':x.get('penalty',{}).get('p_takes_penalty'),'pred_penalty_goals':x.get('penalty',{}).get('expected_penalty_goals'),'actual_penalty_saves':a['penalties_saved'],'actual_penalties_missed':a['penalties_missed'],'actual_cameo':int(not a['starts'] and a['minutes']>0),'keeper':p['position']==1})
 for t in f.get('gk_team_fixtures',[]):
  fx=int(t['fixture_uuid'].split('-')[-1]);game=fixtures[fx]
  if game['event']!=gw:continue
  conservation=t.get('event_conservation',{});pred=conservation.get('team_goals');draws=conservation.get('draws');tid=int(t['team']);teams.append({'gw':gw,'fixture':str(t['fixture_uuid']),'team':tid,'expected_goals':pred/draws if pred is not None and draws else np.nan,'actual_goals':game['team_h_score']if tid==game['team_h']else game['team_a_score'],'scope':'Sampled team goal mean including own-goal events; no team-goal PMF archived here'})
d=d.merge(pd.DataFrame(meta),on=['gw','id'],validate='one_to_one');assert len(d)==2007
for c in ['goals','assists']:
 total=d.groupby(['gw','fixture','team'])['pred_'+c].transform('sum');d['pred_'+c+'_share']=np.where(total>0,d['pred_'+c]/total,np.nan)
d['cohort']=np.select([d.pstart<.2,d.pstart<.9],['low_start','rotation'],default='regular')
d['start_band']=pd.cut(d.pstart,[-.00001,.2,.5,.8,.9,1.00001],right=False).astype(str)
d['goal_share_band']=pd.cut(d.pred_goals_share,[-.00001,.1,.25,.4,1.00001],right=False).astype(str)
d['assist_share_band']=pd.cut(d.pred_assists_share,[-.00001,.1,.25,.4,1.00001],right=False).astype(str)
d['forecast_price_band']=np.where(d.price_tenths>=90,'premium_9m_plus','under_9m')
def metrics(g):
 em=g.xmins-g.minutes;ep=g.xp-g.points
 out={'rows':len(g),'matches':g.fixture.nunique(),'minute_mae':float(abs(em).mean()),'minute_rmse':float(np.sqrt((em**2).mean())),'minute_bias':float(em.mean()),'xp_mae':float(abs(ep).mean()),'xp_rmse':float(np.sqrt((ep**2).mean())),'xp_bias':float(ep.mean()),'crps':float(g.crps.mean()),'goal_bias':float((g.pred_goals-g.actual_goals).mean()),'assist_bias':float((g.pred_assists-g.actual_assists).mean())}
 for e,p,y in [('start',g.pstart,g.started),('positive_minutes',g.pplay,g.minutes.gt(0)),('60',g.p60,g.minutes.ge(60)),('90',g.p90,g.minutes.eq(90))]:
  out[e+'_brier']=float(((p-y)**2).mean());out[e+'_bias']=float((p-y).mean())
 return out
records=[]
for dim in ['all','gw','club','position','cohort','start_band','normal_role','availability','status_at_forecast','forecast_price_band','goal_share_band','assist_share_band']:
 groups=[('all',d)]if dim=='all'else d.groupby(dim,dropna=False)
 for name,g in groups:records.append({'dimension':dim,'group':str(name),**metrics(g)})
pd.DataFrame(records).to_csv(O/'error-atlas.csv',index=False)
players=d.groupby(['id','name']).apply(lambda g:pd.Series(metrics(g)),include_groups=False).reset_index();players.to_csv(O/'player-error-atlas.csv',index=False)
# Cluster intervals only for adequately represented groups; three GWs cannot validate stability.
intervals=[]
for dim in ['all','cohort','position']:
 for name,g in ([('all',d)]if dim=='all'else d.groupby(dim)):
  for metric,values in [('minute_mae',abs(g.xmins-g.minutes)),('xp_mae',abs(g.xp-g.points)),('minute_bias',g.xmins-g.minutes),('xp_bias',g.xp-g.points),('crps',g.crps),('start_brier',(g.pstart-g.started)**2),('p90_brier',(g.p90-g.minutes.eq(90))**2)]:
   z=g.assign(value=values).groupby('fixture').value.agg(['sum','count']).to_numpy();ix=rng.integers(0,len(z),size=(5000,len(z)));b=z[ix].sum(axis=1);ci=np.quantile(b[:,0]/b[:,1],[.025,.975]);intervals.append({'dimension':dim,'group':str(name),'metric':metric,'value':float(values.mean()),'matches':len(z),'ci95_low':ci[0],'ci95_high':ci[1],'method':'paired fixture cluster bootstrap; exploratory; excludes temporal parameter uncertainty'})
pd.DataFrame(intervals).to_csv(O/'uncertainty.csv',index=False)
cal=[]
for dim in ['all','cohort','position']:
 for name,g in ([('all',d)]if dim=='all'else d.groupby(dim)):
  for event,prob,y in [('start',g.pstart,g.started),('60',g.p60,g.minutes.ge(60)),('90',g.p90,g.minutes.eq(90)),('points_10plus',g.p_points_10,g.points.ge(10))]:
   z=pd.DataFrame({'p':prob,'y':y,'bin':np.minimum((prob*10).astype(int),9)})
   for b,h in z.groupby('bin'):cal.append({'dimension':dim,'group':str(name),'event':event,'decile':int(b),'rows':len(h),'predicted':float(h.p.mean()),'observed':float(h.y.mean())})
pd.DataFrame(cal).to_csv(O/'calibration.csv',index=False)
t=pd.DataFrame(teams);t.to_csv(O/'team-goals.csv',index=False);missing_team_rows=int(t.expected_goals.isna().sum());t=t[t.expected_goals.notna()].copy();assert len(t)==20
# Club/player/role observations are descriptive, not hypotheses confirmed by multiple-testing-adjusted tests.
link={'minute_point_error_pearson':float(np.corrcoef(d.xmins-d.minutes,d.xp-d.points)[0,1]),'absolute_minute_point_error_pearson':float(np.corrcoef(abs(d.xmins-d.minutes),abs(d.xp-d.points))[0,1]),'scope':'Observed error association; no causal mediation or MM ablation'}
credited=d.groupby(['gw','fixture','team']).agg(expected_goals=('pred_goals','sum'),actual_goals=('actual_goals','sum'),observed_shot_xg=('observed_shot_xg','sum')).reset_index();credited.to_csv(O/'team-credited-goals.csv',index=False)
teammetrics={'credited_goal_scope':'Excludes own-goal goals credited to opponent; sampled player goal component means aggregated by team','credited_goal_rows':len(credited),'credited_goal_rmse':float(np.sqrt(np.mean((credited.expected_goals-credited.actual_goals)**2))),'credited_goal_bias':float((credited.expected_goals-credited.actual_goals).mean()),'rows':len(t),'matches':t.fixture.nunique(),'missing_explicit_team_law_rows':missing_team_rows,'unavailable_gws':sorted(set([8,9,10])-set(t.gw.unique())),'rmse':float(np.sqrt(np.mean((t.expected_goals-t.actual_goals)**2))),'bias':float((t.expected_goals-t.actual_goals).mean()),'per_gw':{int(gw):{'expected':float(g.expected_goals.sum()),'actual':int(g.actual_goals.sum())}for gw,g in t.groupby('gw')}}
share=[]
for c in ['goals','assists']:
 for band,g in d.groupby(c[:-1]+'_share_band' if c=='goals'else'assist_share_band'):
  share.append({'target':c,'share_band':str(band),'rows':len(g),'matches':g.fixture.nunique(),'predicted':float(g['pred_'+c].sum()),'actual':int(g['actual_'+c].sum()),'observed_shot_xg_or_xa':float(g['observed_shot_xg'if c=='goals'else'observed_shot_xa'].sum()),'xp_bias':float((g.xp-g.points).mean())})
pd.DataFrame(share).to_csv(O/'attacking-share-diagnostic.csv',index=False)
d.to_csv(O/'enriched-player-evaluation.csv',index=False)
(O/'additional-results.json').write_text(json.dumps({'team_goals':teammetrics,'MM_PM_association':link,'evaluated_rows':len(d),'scored_gws':[8,9,10],'unavailable_stratifiers':['verified exact substitution timestamps and causes','cutoff-certified complete future Europa/cup schedule and travel','historical injury diagnosis and explicit return date'],'notes':['Role/availability are archived labels; no inference from current news','Premium cohort uses archived price >=9m; it is not a post-outcome star ranking','Expected goal/assist events are compared with realized goals/FPL assists; observed shot xG/xA is a separate descriptive target','Conditional individual shot xG or xA latent forecasts are not separately identified by sampled goal/assist components','Only three GWs; broad intervals and no population-wide fault declarations']},indent=2))
print(json.dumps({'rows':len(d),'atlas_groups':len(records),'team_goals':teammetrics,'MM_PM_association':link},indent=2))
