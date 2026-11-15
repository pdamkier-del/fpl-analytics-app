"""Prospective paired research forecasts. Never deploys or changes the app model."""
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import replace
import argparse,copy,gzip,hashlib,json,sys,traceback
import numpy as np,pandas as pd
from mm_candidate_forecast import infer_B
from mm_locked_bridge import attach_mm
from run_vfinal_integrated import make_vfinal_input
from gk_joint_bridge import prepare,observations,DurationHistory
from gk_solo_role import SoloRolePolicy,mark_horizon_absences
from joint_role_bridge import apply_assignment
from b_chain_contract import prepare_match
from fpl_v1_1_model.experimental_role_assignment_history import AssignmentHistory
from fpl_v1_1_model.experimental_physical_timeline import PhysicalKernel
from fpl_v1_1_model.experimental_joint_role_assignment import RoleLineup
from fpl_v1_1_model.experimental_joint_substitutions import JointSubstitutionKernel
from fpl_v1_1_model import b_event_simulator as event
ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'analysis/results/joint-substitution-research-20261108/model.json'
PLAN=ROOT/'analysis/results/joint-substitution-research-20261108/prospective-plan.json'

def load(path):return json.loads(Path(path).read_text())
def utc(x):
 value=datetime.fromisoformat(str(x).replace('Z','+00:00'))
 if value.tzinfo is None:raise ValueError('Timezone required')
 return value.astimezone(timezone.utc)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def pack(data):return gzip.compress(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode(),mtime=0)
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False))
def bounds(asof,deadline,now):
 if not utc(asof)<=now<utc(deadline):raise ValueError('Forecast must be issued before deadline and after source cutoff')
 if (now-utc(asof)).total_seconds()>86400:raise ValueError('Stale source snapshot')

def prepare_tasks(source,published):
 source=Path(source);published=Path(published);inputs=source/'work/current-B-inputs';f=load(published/'current/forecast.json');index=load(published/'current/index.json');now=datetime.now(timezone.utc)
 bounds(f['data_asof'],f['origin_deadline'],now)
 if sha(published/'current/forecast.json')!=index['forecast_file_sha256']:raise ValueError('Published forecast checksum mismatch')
 for name,digest in f['input_sha256'].items():
  if sha(inputs/name)!=digest:raise ValueError('Input snapshot mismatch: '+name)
 for name,digest in f['code_sha256'].items():
  if sha(ROOT/name)!=digest:raise ValueError('Numerical code mismatch: '+name)
 h=pd.read_csv(inputs/'history.csv.gz',low_memory=False);target=pd.read_csv(inputs/'target.csv.gz',low_memory=False);prov=load(inputs/'provenance.json');bootstrap=load(inputs/'bootstrap.json');pred,_=infer_B(h,target,prov)
 evidence=source/'work/gk-official-evidence/fpl_bootstrap.json';fresh=load(evidence)if evidence.exists()else bootstrap;pred=mark_horizon_absences(pred,fresh)
 frame=attach_mm(pd.read_csv(inputs/'pm.csv.gz',low_memory=False),pred);gw=int(f['gws'][0]);frame=frame[frame.target_gw.eq(gw)]if 'target_gw'in frame else frame[frame.gw.eq(gw)]
 squads=pd.read_csv(source/'work/joint-gk-current/role-squad-evidence.csv.gz');policy=SoloRolePolicy(h,squads)
 if abs(policy.risk-f['goalkeeper_role_fit']['predictive_other_start_probability'])>1e-10:raise ValueError('Keeper policy mismatch')
 rolehistory=AssignmentHistory(pd.read_csv(inputs/'roles.csv.gz'));strength=f['role_assignment']['strength'];weights=pd.read_csv(source/'work/joint-gk-current/nonpenalty-goal-head.csv.gz').set_index(['fixture_uuid','player_uuid'])
 # Historical core is restored unchanged by the workflow; current observations come from this source artifact only.
 import shutil
 dest=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1';dest.mkdir(parents=True,exist_ok=True)
 for p in (source/'data_v1_1/derived/live_locked_inputs/2026-27-v1').glob('*.csv.gz'):shutil.copyfile(p,dest/p.name)
 obs=observations(ROOT);catalog={int(p['id']):p for p in bootstrap['elements']};out=[];published_rows={}
 for player in f['players']:
  for w in player['weeks']:
   if w['gw']==gw:
    for x in w['fixtures']:published_rows[x['fixture_uuid'],player['player_uuid']]=(player,x)
 keeper_m={ (p['fixture_id'],p['player_id']):p for p in load(published/'gk/gk-mm.json')['players'] }
 for fx,g in frame.groupby('fixture_uuid',sort=True):
  inp,_=make_vfinal_input(g);inp=replace(inp,bps_rules=f['season']);mm=pred[pred.fixture_uuid.eq(fx)].copy()
  official=f['official_gk_evidence'];incomplete=(official['team_id'],)if official['unlisted_competitors']else()
  inp,moments,_=prepare(inp,mm,DurationHistory(obs,str(g.cutoff.iloc[0])),incomplete_teams=incomplete,role_policy=policy,season=f['season'])
  corrected,dist,_=apply_assignment(mm,rolehistory,strength=strength);by=corrected.set_index('player_uuid')
  inp=replace(inp,players=tuple(p if p.is_keeper else replace(p,p_start=float(by.loc[p.player_id,'p']),p_cameo_given_bench=float(by.loc[p.player_id,'q']))for p in inp.players))
  pcatalog={str(r.player_uuid):catalog[int(r.fpl_element)]for r in g.itertuples()};inp=prepare_match(inp,pcatalog)
  inp=replace(inp,players=tuple(replace(p,goal_weight=float(weights.loc[(fx,p.player_id),'ordinary_goal_weight']),penalty_fallback_weight=p.goal_weight)if not p.player_id.startswith('__unlisted_goalkeeper__:')else p for p in inp.players),experimental_conditional_penalties=True)
  base=PhysicalKernel(inp,dist)
  for p in inp.players:
   if p.player_id.startswith('__unlisted_goalkeeper__:'):continue
   _,x=published_rows[fx,p.player_id]
   if p.is_keeper:
    m=keeper_m[fx,p.player_id]
    for key in ['p','x','p60','p90']:
     named={'p':'p_start','x':'xmins','p60':'p_60_plus','p90':'p_90'}[key]
     if abs(moments[p.player_id][key]-m[named])>1e-6:raise ValueError('Keeper marginal parity failed: '+p.player_id+' '+key)
   else:
    for key,named in [('p','p_start'),('x','xmins'),('p60','p_60_plus'),('p90','p_90')]:
     if abs(base.moments[p.player_id][key]-x[named])>1e-6:raise ValueError('Physical baseline parity failed: '+p.player_id+' '+key)
  caps={}
  for p in inp.players:
   if p.is_keeper:continue
   row=by.loc[p.player_id];cap=float(row.availability_cap)if 'availability_cap'in by else 1.
   if 'availability_cap'not in by and bool(row.news_eligible):
    if row.news_state in ['OUT','SUSPENDED']:cap=0.
    elif pd.notna(row.news_chance):cap=float(row.news_chance)/100
   if p.p_start>cap+2e-6:raise ValueError('Availability cap inconsistent with XI')
   caps[p.player_id]=max(cap,p.p_start)
  out.append((fx,inp,dist,caps,published_rows))
 if not out:raise ValueError('No origin fixtures')
 return f,bootstrap,out

def forecast(source,published,ledger,run_id,draws):
 ledger=Path(ledger);model=load(MODEL);plan=load(PLAN)
 if sha(MODEL)!=plan['candidate_model_sha256']:raise ValueError('Frozen candidate model hash changed')
 f,bootstrap,tasks=prepare_tasks(source,published);deadline=f['origin_deadline'];start=datetime.now(timezone.utc);gw=int(f['gws'][0]);stamp=start.strftime('%Y%m%dT%H%M%SZ');rows=[];code={p:sha(ROOT/p)for p in ['src/fpl_v1_1_model/experimental_joint_substitutions.py','scripts/joint_substitution_automation.py']}
 for n,(fx,inp,dist,caps,pub)in enumerate(tasks):
  kernels=[PhysicalKernel(inp,dist),JointSubstitutionKernel(inp,dist,caps,fx,model)];players=list(inp.players);samples=np.zeros((2,len(players),draws),dtype=np.int16);seed=int(hashlib.sha256(fx.encode()).hexdigest()[:8],16)
  for draw in range(draws):
   for arm,k in enumerate(kernels):
    rng=np.random.default_rng(np.random.SeedSequence([20261115,seed,draw,1]));erng=np.random.default_rng(np.random.SeedSequence([20261115,seed,draw,2]));result=event.simulate_match(inp,erng,timeline=k.sample(rng))
    for j,p in enumerate(players):
     r=result[p.player_id];assert r.points==event.legacy.nonbonus_total(event.legacy.point_components(p.position,p.is_keeper,r))+r.bonus;samples[arm,j,draw]=r.points
  for j,p in enumerate(players):
   if p.player_id.startswith('__unlisted_goalkeeper__:'):continue
   person,_=pub[fx,p.player_id];b=kernels[0].moments.get(p.player_id);c=kernels[1].moments.get(p.player_id)
   rows.append({'fixture':fx,'id':person['id'],'player_uuid':p.player_id,'position':person['position'],'code':next(x['code']for x in bootstrap['elements']if x['id']==person['id']),'baseline_points':samples[0,j].tolist(),'candidate_points':samples[1,j].tolist(),'baseline_minutes':b['x']if b else None,'candidate_minutes':c['x']if c else None,'pstart':b['p']if b else None,'baseline_pplay':b['p_play']if b else None,'candidate_pplay':c['p_play']if c else None,'baseline_p90':b['p90']if b else None,'candidate_p90':c['p90']if c else None})
  print('PROSPECTIVE',n+1,'/',len(tasks),fx,flush=True)
 end=datetime.now(timezone.utc);bounds(f['data_asof'],deadline,end);payload={'schema':'joint-substitution-prospective-v1','season':f['season'],'gw':gw,'source_forecast_sha256':f['forecast_sha256'],'source_data_asof':f['data_asof'],'issued_at':end.isoformat(),'deadline':deadline,'candidate_model_sha256':sha(MODEL),'code':code,'workflow_run':run_id,'draws':draws,'baseline_parity_verified':True,'validation_only':False,'rows':rows};raw=pack(payload);folder=ledger/f['season']/('GW'+str(gw));folder.mkdir(parents=True,exist_ok=True);path=folder/(stamp+'-'+run_id+'.json.gz')
 with path.open('xb')as stream:stream.write(raw)
 return {'status':'forecast_archived','gw':gw,'issued_at':end.isoformat(),'deadline':deadline,'rows':len(rows),'sha256':hashlib.sha256(raw).hexdigest(),'file':str(path.relative_to(ledger))}

def score(ledger):
 import requests
 ledger=Path(ledger);bootstrap=requests.get('https://fantasy.premierleague.com/api/bootstrap-static/',timeout=45);bootstrap.raise_for_status();boot=bootstrap.json();events={x['id']:x for x in boot['events']};codes={x['id']:x['code']for x in boot['elements']};chosen={}
 for path in ledger.glob('20??-??/GW*/*.json.gz'):
  d=json.loads(gzip.decompress(path.read_bytes()))
  if d.get('validation_only')or utc(d['issued_at'])>=utc(d['deadline']):continue
  key=d['season'],d['gw'];old=chosen.get(key)
  if old is None or utc(old[1]['issued_at'])<utc(d['issued_at']):chosen[key]=(path,d)
 all_rows=[];rounds=[]
 for (season,gw),(path,d)in sorted(chosen.items()):
  if not events[gw]['finished']or not events[gw]['data_checked']:rounds.append({'gw':gw,'status':'pending_results'});continue
  res=requests.get(f'https://fantasy.premierleague.com/api/event/{gw}/live/',timeout=45);res.raise_for_status();actual={r['id']:r for r in res.json()['elements']};weekrows=[]
  for pid in sorted({r['id']for r in d['rows']}):
   rs=[r for r in d['rows']if r['id']==pid]
   if codes[pid]!=rs[0]['code']:raise ValueError('FPL identity changed')
   point=float(actual[pid]['stats']['total_points']);ps=max((r['pstart']or 0)for r in rs);row={'gw':gw,'id':pid,'rotation':.2<=ps<.9,'regular':ps>=.9,'active':ps>=.2,'fixture_count':len(rs),'actual_points':point}
   for arm in ['baseline','candidate']:
    x=np.sum(np.array([r[arm+'_points']for r in rs],float),axis=0);n=len(x);row[arm+'_xp']=float(x.mean());row[arm+'_crps']=float(abs(x-point).mean()-np.sum((2*np.arange(1,n+1)-n-1)*np.sort(x))/n**2)
   if len(rs)==1 and rs[0]['pstart']is not None:
    r=rs[0];minutes=actual[pid]['stats']['minutes'];row['actual_minutes']=minutes
    for arm in ['baseline','candidate']:row[arm+'_minute_sq']=(r[arm+'_minutes']-minutes)**2;row[arm+'_p90_brier']=(r[arm+'_p90']-int(minutes==90))**2
   weekrows.append(row)
  all_rows.extend(weekrows);rounds.append({'gw':gw,'status':'complete','rows':len(weekrows),'source':str(path.relative_to(ledger))})
 f=pd.DataFrame(all_rows);summary={}
 if len(f):
  for name,g in [('all',f),('active',f[f.active]),('rotation',f[f.rotation]),('regular',f[f.regular])]:
   summary[name]={'rows':len(g)}
   if not len(g):continue
   for arm in ['baseline','candidate']:summary[name][arm]={'crps':float(g[arm+'_crps'].mean()),'xp_mse':float(((g[arm+'_xp']-g.actual_points)**2).mean())}
 uncertainty={}
 if len(f) and f[f.active].gw.nunique()>=2:
  active=f[f.active];rng=np.random.default_rng(20261115)
  for name,delta in [('point_crps',active.candidate_crps-active.baseline_crps),('point_mse',(active.candidate_xp-active.actual_points)**2-(active.baseline_xp-active.actual_points)**2)]:
   blocks=active.assign(delta=delta).groupby('gw').delta.agg(['sum','count']).to_numpy();b=blocks[rng.integers(len(blocks),size=(5000,len(blocks)))].sum(axis=1);uncertainty[name]={'candidate_minus_baseline':float(delta.mean()),'paired_GW_block_ci95':np.quantile(b[:,0]/b[:,1],[.025,.975]).tolist()}
 report={'uncertainty':uncertainty,'schema':'joint-substitution-prospective-evaluation-v1','updated_at':datetime.now(timezone.utc).isoformat(),'rounds':rounds,'summary':summary,'completed_gws':sum(r['status']=='complete'for r in rounds),'promotion':'not_authorised_automatically','app_model_changed':False};save(ledger/'evaluation.json',report);return report

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path);ap.add_argument('--published',type=Path);ap.add_argument('--ledger',type=Path,required=True);ap.add_argument('--run-id',required=True);ap.add_argument('--draws',type=int,default=2048);ap.add_argument('--score-only',action='store_true');a=ap.parse_args();a.ledger.mkdir(parents=True,exist_ok=True)
 status={'run_id':a.run_id,'updated_at':datetime.now(timezone.utc).isoformat(),'app_model_changed':False}
 try:
  if not a.score_only:status['capture']=forecast(a.source,a.published,a.ledger,a.run_id,a.draws)
  status['evaluation']=score(a.ledger);status['status']='success';save(a.ledger/'status.json',status)
 except Exception as e:
  status.update(status='failed',error_type=type(e).__name__,message=str(e).split('?')[0][:500]);save(a.ledger/'status.json',status);raise
if __name__=='__main__':main()
