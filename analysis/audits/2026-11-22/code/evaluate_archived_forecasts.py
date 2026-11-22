"""Read-only evaluation of immutable public GW8/9 forecasts and official FPL results."""
from pathlib import Path
import json,hashlib,gzip
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'inputs/archive'
OUT=ROOT/'results';OUT.mkdir(exist_ok=True)
def raw(p):return gzip.decompress(p.with_name(p.name+'.gz').read_bytes())
def read(p):return json.loads(raw(p))
MAP={'minutes':'appearance_points','goals_scored':'goal_points','assists':'assist_points','clean_sheets':'cs_points','goals_conceded':'gc_points','saves':'save_points','penalties_saved':'penalty_save_points','defensive_contribution':'dc_points','bonus':'expected_bonus','yellow_cards':'negative_points','red_cards':'negative_points','own_goals':'negative_points','penalties_missed':'negative_points'}
COMP=list(dict.fromkeys(MAP.values()));rows=[];samples=[];meta=[]
report=read(R/'report.json');current=read(R/'bootstrap.json');nowplayers={p['id']:p for p in current['elements']}
assert all(next(e for e in current['events']if e['id']==gw)['data_checked'] for gw in [8,9,10])
for gw in [8,9,10]:
 f=read(R/f'gw{gw}-forecast.json');ix=read(R/f'gw{gw}-index.json');m=read(R/f'gw{gw}-mm.json');docs=read(R/f'gw{gw}-existing-app-data.json')
 receipt=next(w for w in report['weeks']if w['gw']==gw)
 assert f['forecast_sha256']==ix['forecast_sha256']==receipt['forecast_sha256']
 for name,key in [('forecast.json','forecast_file_sha256'),('mm.json','mm_file_sha256'),('existing-app-data.json','existing_app_data_sha256')]:assert hashlib.sha256(raw(R/f'gw{gw}-{name}')).hexdigest()==ix[key]
 assert pd.Timestamp(f['data_asof'])<=pd.Timestamp(receipt['published_at'])<pd.Timestamp(f['origin_deadline'])
 mm={(r['player_id'],r['fixture_id']):r for r in m['players']};live={p['id']:p for p in read(R/f'gw{gw}-live.json')['elements']};cat={p['id']:p for p in docs['documents']['current-players.json']['players']}
 count=0
 for p in f['players']:
  w=next(w for w in p['weeks']if w['gw']==gw);assert len(w['fixtures'])==1,'Need per-fixture labels for DGW'
  fx=w['fixtures'][0];a=live[p['id']];stats=a['stats'];assert cat[p['id']]['code']==nowplayers[p['id']]['code']
  value={c:0. for c in COMP};explain=next(e for e in a['explain']if str(e['fixture'])==fx['fixture_uuid'].split('-')[-1])
  for s in explain['stats']:
   assert s['identifier']in MAP,s['identifier'];assert not s.get('points_modification',0),'Requires modified-score audit'
   value[MAP[s['identifier']]]+=s['points']
  assert sum(value.values())==stats['total_points']
  assert abs(sum(fx['components'].values())-fx['xpts'])<1e-8
  sc=w['scenarios'];pts=np.asarray(sc['points'],float);mins=np.asarray(sc['minutes'],float);assert len(pts)==len(mins)==400
  assert abs(pts.mean()-fx['xpts'])<1e-8
  mr=mm[p['player_uuid'],fx['fixture_uuid']];ps=fx['p_start'];q=fx['q_sub'];s=mr['start_minutes'];c=mr['sub_minutes'];assert abs(ps*s+(1-ps)*q*c-fx['xmins'])<1e-6
  st=int(stats['starts']);minute=stats['minutes'];actual=stats['total_points'];row=dict(gw=gw,fixture=fx['fixture_uuid'],id=p['id'],name=p['name'],position=p['position'],status_at_forecast=cat[p['id']].get('status'),minutes=minute,started=st,points=actual,xmins=fx['xmins'],xp=fx['xpts'],pstart=ps,pplay=mr['p_play'],p60=fx['p_60_plus'],p90=fx['p_90'],q_sub=q,oracle_start_xmins=st*s+(1-st)*q*c,oracle_start_supported=(ps>1e-12 if st else ps<1-1e-12))
  row['crps']=float(abs(pts-actual).mean()-np.sum((2*np.arange(1,len(pts)+1)-len(pts)-1)*np.sort(pts))/len(pts)**2)
  lo,hi=fx['distribution']['points_interval80'];row.update(interval80_predicted_mass=float(((pts>=lo)&(pts<=hi)).mean()),interval80_low=lo,interval80_high=hi,interval80_covered=lo<=actual<=hi,interval80_width=hi-lo,points_outside_sample_support=actual<pts.min()or actual>pts.max())
  # Exact empirical conditional expectation given coarse observed minutes, not a deployable forecast or a full causal oracle.
  bins=np.where(mins==0,0,np.where(mins<60,1,np.where(mins<90,2,3)));bin_actual=0 if minute==0 else 1 if minute<60 else 2 if minute<90 else 3
  selected=pts[bins==bin_actual];row['oracle_minute_bin_samples']=len(selected);row['oracle_minute_bin_xp']=float(selected.mean())if len(selected)>=30 else np.nan
  for event,threshold in [('2',2),('5',5),('10',10)]:row['p_points_'+event]=float((pts>=threshold).mean())
  for component in COMP:
   row['pred_'+component]=fx['components'][component];row['actual_'+component]=value[component]
  rows.append(row);samples.append((gw,fx['fixture_uuid'],p['id'],pts));count+=1
 assert count==receipt['scored_rows']
 meta.append({'gw':gw,'rows':count,'published_at':receipt['published_at'],'cutoff':f['data_asof'],'forecast_sha256':f['forecast_sha256'],'model_code_sha256':f['code_sha256'],'archive_basis':receipt['archive_basis']})
d=pd.DataFrame(rows);assert len(d)==2007;assert not d.duplicated(['gw','fixture','id']).any()
def metrics(g):
 e=g.xmins-g.minutes;ep=g.xp-g.points
 return {'n':len(g),'fixtures':g.fixture.nunique(),'minute_mae':float(abs(e).mean()),'minute_rmse':float(np.sqrt((e**2).mean())),'minute_bias':float(e.mean()),'xp_mae':float(abs(ep).mean()),'xp_rmse':float(np.sqrt((ep**2).mean())),'xp_bias':float(ep.mean()),'mean_crps':float(g.crps.mean()),'interval80_coverage':float(g.interval80_covered.mean()),'interval80_predicted_mass':float(g.interval80_predicted_mass.mean()),'interval80_width':float(g.interval80_width.mean())}
groups={'all':d,'active':d[d.pstart>=.2],'rotation':d[(d.pstart>=.2)&(d.pstart<.9)],'regular':d[d.pstart>=.9]}
for pos,name in [(1,'GK'),(2,'DEF'),(3,'MID'),(4,'FWD')]:groups[name]=d[d.position==pos]
summary={k:metrics(v)for k,v in groups.items()};per_gw={int(gw):metrics(g)for gw,g in d.groupby('gw')}
events=[];reliability=[]
for name,prob,y in [('start',d.pstart,d.started),('play',d.pplay,d.minutes.gt(0)),('60',d.p60,d.minutes.ge(60)),('90',d.p90,d.minutes.eq(90)),*[(f'points_ge_{t}',d[f'p_points_{t}'],d.points.ge(int(t)))for t in ['2','5','10']]]:
 events.append({'event':name,'n':len(d),'predicted':float(prob.mean()),'observed':float(y.mean()),'bias':float((prob-y).mean()),'brier':float(((prob-y)**2).mean())})
 frame=pd.DataFrame({'p':prob,'y':y,'bin':np.minimum((prob*5).astype(int),4)})
 for b,g in frame.groupby('bin'):reliability.append({'event':name,'bin':int(b),'n':len(g),'predicted':float(g.p.mean()),'observed':float(g.y.mean())})
components=[];oracle=[];rng=np.random.default_rng(20261108)
def paired_interval(frame,delta):
 groups=frame.assign(delta=delta).groupby('fixture').delta.agg(['sum','count']).to_numpy();b=groups[rng.integers(len(groups),size=(5000,len(groups)))].sum(axis=1)
 return {'delta':float(delta.mean()),'match_cluster_ci95':np.quantile(b[:,0]/b[:,1],[.025,.975]).tolist()}
for name,g in [('all',d),*[(n,groups[n])for n in ['GK','DEF','MID','FWD']]]:
 for c in COMP:
  a=g['actual_'+c];p=g['pred_'+c];components.append({'group':name,'component':c,'n':len(g),'predicted_total':float(p.sum()),'actual_total':float(a.sum()),'bias_per_player':float((p-a).mean()),'mae':float(abs(p-a).mean()),'mse':float(((p-a)**2).mean())})
for c in COMP:
 fixed=d.xp-d['pred_'+c]+d['actual_'+c];without=d.xp-d['pred_'+c];base=(d.xp-d.points)**2
 oracle.append({'component':c,'perfect_component':paired_interval(d,(fixed-d.points)**2-base),'component_zeroed':paired_interval(d,(without-d.points)**2-base)})
# Group components before ranking; effects are not additive because errors covary.
for name,cs in {'attack':['goal_points','assist_points'],'defence':['cs_points','gc_points','save_points','penalty_save_points'],'appearance':['appearance_points'],'dc':['dc_points'],'bonus':['expected_bonus']}.items():
 fixed=d.xp-sum(d['pred_'+c]for c in cs)+sum(d['actual_'+c]for c in cs);oracle.append({'component_group':name,'perfect_component':paired_interval(d,(fixed-d.points)**2-(d.xp-d.points)**2)})
o=d[d.oracle_start_supported];e0=o.xmins-o.minutes;e1=o.oracle_start_xmins-o.minutes
start_oracle={'supported_rows':len(o),'unsupported_rows':int((~d.oracle_start_supported).sum()),'baseline_mae':float(abs(e0).mean()),'oracle_start_mae':float(abs(e1).mean()),'baseline_rmse':float(np.sqrt((e0**2).mean())),'oracle_start_rmse':float(np.sqrt((e1**2).mean())),'paired_mse':paired_interval(o,e1**2-e0**2),'scope':'Exact archived individual duration mixture conditional on realized start, not a joint lineup rerun or a point oracle'}
o=d[d.oracle_minute_bin_samples>=30];delta=(o.oracle_minute_bin_xp-o.points)**2-(o.xp-o.points)**2
minute_oracle={'supported_rows':len(o),'excluded_rows':len(d)-len(o),'baseline_mae':float(abs(o.xp-o.points).mean()),'oracle_minute_bin_mae':float(abs(o.oracle_minute_bin_xp-o.points).mean()),'baseline_rmse':float(np.sqrt(((o.xp-o.points)**2).mean())),'oracle_minute_bin_rmse':float(np.sqrt(((o.oracle_minute_bin_xp-o.points)**2).mean())),'paired_mse':paired_interval(o,delta),'scope':'Conditional archived point draws given observed minutes bin0/1-59/60-89/90; >=30 draws; no exact start flags or full conditional simulation stored; support-selection and Monte Carlo limitations'}
# Exact empirical CRPS comparison against ablation of all dispersion (point mass at the forecast mean).
dist_test={'mean_crps':float(d.crps.mean()),'degenerate_at_mean_crps':float(abs(d.xp-d.points).mean()),'scope':'Distribution versus point-mass baseline, not a competing probabilistic football model','sample_support_misses':int(d.points_outside_sample_support.sum())}
subgroup_events=[]
for group,g in groups.items():
 for event,prob,y in [('start',g.pstart,g.started),('play',g.pplay,g.minutes.gt(0)),('60',g.p60,g.minutes.ge(60)),('90',g.p90,g.minutes.eq(90))]:
  subgroup_events.append({'group':group,'event':event,'n':len(g),'predicted':float(prob.mean()),'observed':float(y.mean()),'brier':float(((prob-y)**2).mean())})
per_gw_components=[]
for gw,h in d.groupby('gw'):
 for group,g in [('all',h),*[(name,h[h.position==pos])for pos,name in [(1,'GK'),(2,'DEF'),(3,'MID'),(4,'FWD')]]]:
  for c in COMP:per_gw_components.append({'gw':int(gw),'group':group,'component':c,'predicted':float(g['pred_'+c].sum()),'actual':float(g['actual_'+c].sum())})
start_groups={}
for group,g in groups.items():
 g=g[g.oracle_start_supported];e0=g.xmins-g.minutes;e1=g.oracle_start_xmins-g.minutes
 start_groups[group]={'n':len(g),'baseline_mae':float(abs(e0).mean()),'oracle_start_mae':float(abs(e1).mean())}
bench=d[d.started==0]
bench_diagnostic={'n':len(bench),'predicted_cameo_given_bench':float(bench.q_sub.mean()),'observed_cameo_given_bench':float((bench.minutes>0).mean())}
code_diff={k:[m['model_code_sha256'].get(k)for m in meta]for k in set().union(*(set(m['model_code_sha256'])for m in meta))if len({m['model_code_sha256'].get(k)for m in meta})>1}
result={'meta':meta,'summary':summary,'per_gw':per_gw,'events':events,'reliability':reliability,'components':components,'sensitivity_oracles':oracle,'start_oracle':start_oracle,'minute_bin_point_oracle':minute_oracle,'distribution':dist_test,'subgroup_events':subgroup_events,'per_gw_components':per_gw_components,'start_oracle_by_group':start_groups,'bench_diagnostic':bench_diagnostic,'changed_model_code_between_gws':code_diff,'limits':['Only GW8–10; changing published model versions, not a fixed-model independent holdout','No parameter refitting or activation','Removing components is a zero-contribution diagnostic, not a valid retrained ablation','Perfect-component corrections use actual outcomes; effects are not additive or deployable','Only individual sampled minutes and points were archived, so exact-start point oracle and true feature ablations require archived replay inputs','Match bootstrap does not capture all cross-match or temporal dependence'],'production_changed':False}
d.to_csv(OUT/'player-evaluation.csv',index=False);pd.DataFrame(components).to_csv(OUT/'component-evaluation.csv',index=False);(OUT/'evaluation.json').write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps({k:result[k]for k in ['summary','events','start_oracle','minute_bin_point_oracle','distribution']},indent=2))
