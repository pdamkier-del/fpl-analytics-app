"""Read-only scoring of immutable original forecasts. No model imports or fitting."""
from datetime import datetime,timezone
import hashlib,json,math
import numpy as np,pandas as pd
from .ts_capture import ledger
MAP={'minutes':'appearance_points','goals_scored':'goal_points','assists':'assist_points','clean_sheets':'cs_points','goals_conceded':'gc_points','saves':'save_points','penalties_saved':'penalty_save_points','defensive_contribution':'dc_points','bonus':'expected_bonus','yellow_cards':'negative_points','red_cards':'negative_points','own_goals':'negative_points','penalties_missed':'negative_points'}
COMP=list(dict.fromkeys(MAP.values()));POS={1:'GK',2:'DEF',3:'MID',4:'FWD'}

def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def crps(samples,y):
 x=np.sort(np.asarray(samples,float));n=len(x)
 if n<2 or not np.isfinite(x).all():raise ValueError('Point scenarios unavailable')
 return float(np.mean(abs(x-y))-np.sum((2*np.arange(1,n+1)-n-1)*x)/n**2)
def probability(x):
 if not isinstance(x,(int,float))or not math.isfinite(x)or not 0<=x<=1:raise ValueError('Invalid probability')
 return x

def validate_bundle(bundle):
 f=bundle['forecast'];receipt=bundle['receipt'];raw={k:v for k,v in f.items()if k!='forecast_sha256'}
 if digest(raw)!=f.get('forecast_sha256'):raise ValueError('Forecast seal mismatch')
 gw=min(f['gws']);asof=ledger.clock(f['data_asof']);published=ledger.clock(receipt['published_at']);deadline=ledger.clock(f['origin_deadline'])
 if not asof<=published<deadline:raise ValueError('Not an original predeadline forecast')
 if not receipt.get('publication_commit')or receipt.get('archive_basis')!='original_public_forecast_snapshot':raise ValueError('Original publication witness missing')
 if receipt.get('forecast_sha256')!=f['forecast_sha256']or bundle['documents']['forecast_sha256']!=f['forecast_sha256']:raise ValueError('Bundle identity mismatch')
 if f.get('season')!=bundle['season']:raise ValueError('Season mismatch')
 return gw

def score(bundle,labels):
 gw=validate_bundle(bundle);f=bundle['forecast'];event=labels['event']
 if labels.get('season')!=f['season']or event.get('id')!=gw:raise ValueError('Outcome season/GW mismatch')
 if not(event.get('finished')is True and event.get('data_checked')is True):return {'schema':'fpl-operational-evaluation-v1','gw':gw,'status':'pending_results','forecast_sha256':f['forecast_sha256'],'scored_rows':0}
 cat=bundle['documents']['documents']['current-players.json'];catalog={p['id']:p for p in cat['players']};mm={(r['player_id'],r['fixture_id']):r for r in bundle['mm']['players']};actual={(r['fixture'],r['id']):r for r in labels['rows']};codes={p['id']:p['code']for p in labels['identities']};fixtures={p['id']:p for p in labels['fixtures']};fr=[];pr=[];missing=[]
 next_ok=cat.get('next_gw')==gw and[e['id']for e in cat.get('events',[])if e.get('is_next')]==[gw]and ledger.clock(cat['fetched_at'])<=ledger.clock(f['data_asof'])
 for p in f['players']:
  if p['id']not in catalog or codes.get(p['id'])!=catalog[p['id']].get('code'):missing.append({'id':p['id'],'reason':'identity_missing_or_changed'});continue
  weeks=[w for w in p['weeks']if w['gw']==gw]
  if len(weeks)!=1:raise ValueError('Duplicate or missing origin week')
  w=weeks[0];results=[];roles=[];starts=[];local=[]
  wanted={int(x['fixture_uuid'].split('-')[-1])for x in w['fixtures']};scheduled={x['id']for x in fixtures.values()if x.get('event')==gw and p['team_id']in[x['team_h'],x['team_a']]}
  if wanted!=scheduled:missing.append({'id':p['id'],'reason':'schedule_changed_after_forecast'});continue
  for x in w['fixtures']:
   fixture=int(x['fixture_uuid'].split('-')[-1]);a=actual.get((fixture,p['id']));game=fixtures.get(fixture)
   if a is None or game is None or not game.get('finished')or game.get('event')!=gw or p['team_id']not in[game['team_h'],game['team_a']]:break
   if a.get('team_id')!=p['team_id']:break
   s=a['stats'];value={c:0. for c in COMP}
   for item in a['explain']:
    if item['identifier']not in MAP or item.get('points_modification',0):raise ValueError('Unknown or modified scoring event')
    value[MAP[item['identifier']]]+=item['points']
   if sum(value.values())!=s['total_points']:raise ValueError('Official component ledger mismatch')
   m=mm[p['player_uuid'],x['fixture_uuid']];ps=probability(x['p_start']);roles.append(m.get('normal_role','unavailable'));starts.append(ps)
   q=probability(x['distribution']['p_60_plus']);factor=4 if p['position']in[1,2]else 1 if p['position']==3 else 0;z=x['components']['cs_points']/factor if factor else 0;c=z/q if q and factor else None
   if c is not None and not -1e-10<=c<=1+1e-10:raise ValueError('CS component and qualification inconsistent')
   row={'gw':gw,'fixture':fixture,'id':p['id'],'club':p['team'],'position':POS[p['position']],'role':roles[-1],'minutes':s['minutes'],'xmins':x['xmins'],'started':s['starts'],'pstart':ps,'p60':probability(x['p_60_plus']),'p90':probability(x['p_90']),'xp':x['xpts'],'points':s['total_points'],'observed_bps':s['bps'],'qualification_probability':q,'cs_qualification_error':factor*c*(q-int(s['minutes']>=60))if c is not None else None,'cs_conditional_error':factor*(c*int(s['minutes']>=60)-value['cs_points']/factor)if c is not None else None}
   if abs(sum(x['components'].values())-x['xpts'])>1e-7:raise ValueError('Forecast components do not sum to xP')
   for comp in COMP:row['pred_'+comp]=x['components'][comp];row['actual_'+comp]=value[comp]
   local.append(row);results.append(s['total_points'])
  else:
   # A blank must be explicit and agree with the official schedule, never a missing label.
   if not w['fixtures']and any(g.get('event')==gw and p['team_id']in[g['team_h'],g['team_a']]for g in fixtures.values()):raise ValueError('Claimed blank contradicts schedule')
   samples=w.get('scenarios',{}).get('points');xp=w['xpts'];actual_points=sum(results)
   if samples is None:raise ValueError('Original point scenarios missing; no regenerated distribution allowed')
   if abs(float(np.mean(samples))-xp)>1e-7 or abs(sum(x['xpts']for x in w['fixtures'])-xp)>1e-7:raise ValueError('Archived point sample/mean mismatch')
   ep=pd.to_numeric(catalog[p['id']].get('ep_next'),errors='coerce')if next_ok else np.nan
   pr.append({'gw':gw,'id':p['id'],'club':p['team'],'position':POS[p['position']],'role':roles[0]if len(set(roles))==1 else'mixed'if roles else'blank','xp':xp,'points':actual_points,'crps':crps(samples,actual_points),'ep_next':float(ep)if np.isfinite(ep)else None});fr.extend(local);continue
  missing.append({'id':p['id'],'reason':'fixture_label_missing_or_identity_mismatch'})
 d=pd.DataFrame(fr);points=pd.DataFrame(pr)
 if points.empty:return {'schema':'fpl-operational-evaluation-v1','gw':gw,'status':'missing_labels','scored_rows':0,'missing':missing,'forecast_sha256':f['forecast_sha256']}
 def point_metrics(g):
  e=g.xp-g.points;return {'rows':len(g),'xp_mae':float(abs(e).mean()),'xp_rmse':float(np.sqrt((e**2).mean())),'xp_bias':float(e.mean()),'crps':float(g.crps.mean())}
 def minute_metrics(g):
  if g.empty:return {'fixture_rows':0}
  e=g.xmins-g.minutes;out={'fixture_rows':len(g),'minute_mae':float(abs(e).mean()),'minute_rmse':float(np.sqrt((e**2).mean()))}
  for name,pcol,y in [('start','pstart',g.started),('60','p60',g.minutes.ge(60)),('90','p90',g.minutes.eq(90))]:out[name]={'brier':float(((g[pcol]-y)**2).mean()),'predicted':float(g[pcol].mean()),'observed':float(y.mean()),'bias':float((g[pcol]-y).mean())}
  return out
 groups=[]
 for dim in ['all','position','club','role']:
  for key,g in ([('all',points)]if dim=='all'else points.groupby(dim)):
   sub=d if dim=='all'else d[d[dim]==key];groups.append({'dimension':dim,'group':str(key),'points':point_metrics(g),'minutes':minute_metrics(sub)})
 components=[]
 for dim in ['all','position']:
  for key,g in ([('all',d)]if dim=='all'else d.groupby(dim)):
   for c in COMP:components.append({'dimension':dim,'group':str(key),'component':c,'predicted':float(g['pred_'+c].sum()),'actual':float(g['actual_'+c].sum()),'mae':float(abs(g['pred_'+c]-g['actual_'+c]).mean())})
 calibration=[]
 for name,col,y in [('60','p60',d.minutes.ge(60)),('90','p90',d.minutes.eq(90))]:
  z=pd.DataFrame({'p':d[col],'y':y});z['bin']=np.minimum((z.p*10).astype(int),9)
  for k,g in z.groupby('bin'):calibration.append({'event':name,'decile':int(k),'rows':len(g),'predicted':float(g.p.mean()),'observed':float(g.y.mean())})
 matched=points[points.ep_next.notna()];benchmark=None
 if len(matched):
  e=matched.ep_next-matched.points;benchmark={'rows':len(matched),'missing':len(points)-len(matched),'model_mae':float(abs(matched.xp-matched.points).mean()),'model_rmse':float(np.sqrt(((matched.xp-matched.points)**2).mean())),'official_mae':float(abs(e).mean()),'official_rmse':float(np.sqrt((e**2).mean())),'scope':'Official ep_next from original same-cutoff catalogue; not current values'}
 return {'schema':'fpl-operational-evaluation-v1','season':f['season'],'gw':gw,'status':'complete'if not missing else'partial_missing_labels','forecast_sha256':f['forecast_sha256'],'publication':bundle['receipt'],'outcome_sha256':digest(labels),'scored_rows':len(points),'forecast_player_rows':len(f['players']),'fixture_rows':len(d),'missing':missing,'summary':{'points':point_metrics(points),'minutes':minute_metrics(d)},'groups':groups,'components':components,'calibration':calibration,'clean_sheet_qualification':{'supported_rows':int(d.cs_conditional_error.notna().sum()),'qualification_error':float(d.cs_qualification_error.sum()),'conditional_cs_error':float(d.cs_conditional_error.sum()),'scope':'Outcome-conditioned diagnostic, not a candidate correction'},'bps':{'forecast_score_status':'not_identified','reason':'Original public forecast contains bonus components, not a background-BPS point distribution; BPS error is not invented','observed_bps_total':float(d.observed_bps.sum()),'bonus_scored':True},'official_ep_next':benchmark,'production_changed':False,'model_refitted':False,'point_scope':'Player/GW joint scenarios; minute scores are per fixture; DGW not treated as one 90-minute match'}
