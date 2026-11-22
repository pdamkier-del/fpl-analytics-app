"""Registered EXP-TS-SEARCH-001 run. Hard 120s initial wall budget, no fitting.

Run from a clean, independent checkout of the pinned numerical source, not app
modules from the research branch. Results append/checkpoint to a new directory.
"""
import argparse,hashlib,importlib,json,os,platform,signal,subprocess,sys,time,traceback
from pathlib import Path
from dataclasses import asdict
PROCESS_START=time.perf_counter()
import numpy as np
import pandas as pd
from reference import (legal_squads,deterministic_best,restricted_best,scalar_score,
                       exact_path,transition,legal_nomination)
S=Path(__file__).resolve().parents[1];ROOT=S.parents[1];PIN='161b67b6fb8786a38e78c245b92a03ad841575d8'
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
 temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n');temp.replace(p)
def forecast(case):
 f=dict(model='B-MM-PM-TS-v1',scope='prospective_preview',locked_model_active=False,synthetic_research_fixture=True,gws=list(range(1,7)),minute_sampler_audit=dict(sampler='B-MM-PM-TS-v1',all_MM_to_PM_means_consistent=True),scenario_contract=dict(version='shared-PM-match-draws-v1',draws=len(case['players'][0]['points'][0])),players=[])
 for p in case['players']:
  weeks=[]
  for g in range(6):
   xm=float(np.mean(p['minutes'][g]));weeks.append(dict(gw=g+1,xpts=float(np.mean(p['points'][g])),p_play=float(np.mean(np.array(p['minutes'][g])>0)),xmins=xm,pm_analytic_minutes=xm,fixtures=[dict(xmins=xm,pm_analytic_minutes=xm)],scenarios=dict(points=p['points'][g],minutes=p['minutes'][g])))
  f['players'].append(dict(id=p['id'],position=p['position'],name='Synthetic'+str(p['id']),team_id=p['team'],price_tenths=p['price'],weeks=weeks))
 return f

def arbitrary_frozen_score(module,ids,positions,points,minutes,nom):
 # The exact unmodified autosub primitive used in ScenarioScorer.decision.
 # Apply its captain semantics per aligned scenario, without a new risk model.
 xi,bench,c,v=nom;ix={p:i for i,p in enumerate(ids)};plays=minutes>0
 base=module.autosub_points(points,plays,np.array([{1:'GKP',2:'DEF',3:'MID',4:'FWD'}[p]for p in positions]),[ix[p]for p in xi],[ix[p]for p in bench])
 return float(np.mean(base+points[:,ix[c]]+np.where(~plays[:,ix[c]],points[:,ix[v]],0.)))

def load_frozen(path):
 manifest=json.loads((S/'inputs/source-manifest.json').read_text())
 assert subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()==PIN
 for p,h in manifest['files'].items():assert digest(path/p)==h,('Frozen source changed',p)
 sys.path[:0]=[str(path/'scripts'),str(path/'src'),str(path)]
 planner=importlib.import_module('fpl_xpts.transfer_planner');season=importlib.import_module('fpl_xpts.season_replay');scoring=importlib.import_module('b_preview_ts');live=importlib.import_module('run_live_locked_ts');config=importlib.import_module('run_joint_fh_wc_stopping_replay').cfg()
 assert json.loads(json.dumps(asdict(config)))==manifest['configuration']
 for module in [planner,season,scoring,live]:assert Path(module.__file__).resolve().is_relative_to(path.resolve())
 return planner,season,scoring,live,config,manifest

def run_case(case,planner,season,scoring,live,config):
 start=time.perf_counter();players={p['id']:p for p in case['players']};ids0=tuple(case['initial_ids']);f=forecast(case);meta,origin=live.project(f);squads=legal_squads(players)
 assert len(players)<=17 and len(squads)>0 and max(len(set(a)-set(b))for a in squads for b in squads)<=2
 assert len(f['gws'])==6 and len(f['players'][0]['weeks'][0]['scenarios']['points'])<=8
 state=season.ReplayState({p:season.OwnedPlayer(p,players[p]['purchase'])for p in ids0},case['bank'],case['free_transfers']);before=asdict(state)
 row=dict(id=case['id'],level=case['level'],family=case['family'],pool=len(players),scenarios=f['scenario_contract']['draws'],legal_squads=len(squads),nomination_domain=case['nomination_domain'],illegal_decisions=[],scorer_disagreements=[],menu_failures=[],nomination_counts=[],score_audits=0)
 fixed=[{}for _ in range(6)];joint=[{}for _ in range(6)];policies={};heur_policies={}
 with scoring.preview_scoring(f)as score:
  t=time.perf_counter();heuristic=planner.plan_transfer_path(state,meta,origin,1,config);row['heuristic_seconds']=time.perf_counter()-t
  assert before==asdict(state),'Input state mutated'
  row['heuristic']=asdict(heuristic)
  for g in range(6):
   for ids in squads:
    positions=tuple(players[p]['position']for p in ids);points=np.array([players[p]['points'][g]for p in ids]).T;minutes=np.array([players[p]['minutes'][g]for p in ids]).T
    h=score.decision(g+1,ids);hnom=h[:4];heur_policies[g,ids]=hnom;fixed[g][ids]=h[-1]
    if not legal_nomination(ids,positions,hnom):row['illegal_decisions'].append(dict(gw=g+1,ids=ids,nomination=hnom))
    hvalue=arbitrary_frozen_score(scoring,ids,positions,points,minutes,hnom);ind=scalar_score(ids,positions,points,minutes,hnom);row['score_audits']+=1
    if max(abs(hvalue-h[-1]),abs(ind-hvalue))>1e-9:row['scorer_disagreements'].append(dict(gw=g+1,ids=ids,kind='heuristic_nomination_score',decision=h[-1],frozen_arbitrary=hvalue,independent=ind))
    if case['level']=='deterministic':
     value,nom,count=deterministic_best(ids,positions,points.mean(axis=0));fv=arbitrary_frozen_score(scoring,ids,positions,points,minutes,nom);sv=scalar_score(ids,positions,points,minutes,nom);row['score_audits']+=1
     if max(abs(value-fv),abs(sv-fv))>1e-9:row['scorer_disagreements'].append(dict(gw=g+1,ids=ids,kind='deterministic_exact_score',algebra=value,frozen=fv,independent=sv))
     value=fv # The original frozen score, never the independent rule cross-check.
    else:
     if list(hnom[0])not in case['xi_menu']:row['menu_failures'].append(dict(gw=g+1,ids=ids,heuristic_xi=hnom[0]))
     value,nom,count,audits,bad=restricted_best(ids,positions,points,minutes,case['xi_menu'],lambda n:arbitrary_frozen_score(scoring,ids,positions,points,minutes,n));row['score_audits']+=audits
     row['scorer_disagreements'].extend(dict(gw=g+1,ids=ids,**x)for x in bad)
    assert legal_nomination(ids,positions,nom);joint[g][ids]=value;policies[g,ids]=nom;row['nomination_counts'].append(dict(gw=g+1,ids=ids,legal_nominations=count))
  # Independent replay checks of all actual heuristic decisions and transitions.
  purchases=tuple(sorted((p,players[p]['purchase'])for p in ids0));bank=case['bank'];ft=case['free_transfers'];value=0.;nom_gain=0.;state_ids=set(ids0)
  if len(heuristic.path)!=6:row['illegal_decisions'].append(dict(kind='incomplete_horizon'))
  for g,a in enumerate(heuristic.path):
   selected=tuple(sorted((state_ids-set(a.outgoing))|set(a.incoming)))
   if selected not in fixed[g]or a.transfers>2 or len(a.incoming)!=len(a.outgoing):row['illegal_decisions'].append(dict(gw=g+1,kind='illegal_transfer_set'));continue
   move=transition(purchases,bank,ft,selected,players)
   if move is None:row['illegal_decisions'].append(dict(gw=g+1,kind='unaffordable'));continue
   after,out,inc,hits,paid=move
   expected=dict(outgoing=out,incoming=inc,bank_before=bank,bank_after=after[1],free_transfers_before=ft,free_transfers_after=after[2],official_hit_points=hits,uncertainty_penalty=config.hit_uncertainty_buffer*paid)
   for k,v in expected.items():
    if getattr(a,k)!=v:row['illegal_decisions'].append(dict(gw=g+1,kind='state_or_cost_mismatch',field=k,expected=v,actual=getattr(a,k)))
   if abs(a.projected_manager_score-fixed[g][selected])>1e-9:row['scorer_disagreements'].append(dict(gw=g+1,kind='planner_vs_frozen_score'))
   if abs(a.utility_this_gw-(fixed[g][selected]-hits-config.hit_uncertainty_buffer*paid))>1e-9:row['scorer_disagreements'].append(dict(gw=g+1,kind='action_utility'))
   value+=config.weights[g]*fixed[g][selected]-hits-config.hit_uncertainty_buffer*paid;nom_gain+=config.weights[g]*(joint[g][selected]-fixed[g][selected]);purchases,bank,ft=after;state_ids=set(selected)
  if abs(value-heuristic.objective)>1e-9:row['scorer_disagreements'].append(dict(kind='path_objective',independent=value,frozen=heuristic.objective))
  row['heuristic_replayed_objective']=value;row['nomination_gain_on_heuristic_path']=nom_gain
 t=time.perf_counter();row['fixed_nomination_exact']=exact_path(case,players,squads,fixed,config.weights,config.hit_uncertainty_buffer);row['joint_exact']=exact_path(case,players,squads,joint,config.weights,config.hit_uncertainty_buffer);row['reference_seconds']=time.perf_counter()-t
 for label in ['fixed_nomination_exact','joint_exact']:
  for a in row[label]['path']:
   key=(a['gw']-1,tuple(a['ids']));a['nomination']=policies[key]if label=='joint_exact'else heur_policies[key]
 row['fixed_nomination_search_gap']=row['fixed_nomination_exact']['objective']-heuristic.objective;row['joint_gap']=row['joint_exact']['objective']-heuristic.objective;row['additional_joint_nomination_opportunity']=row['joint_exact']['objective']-row['fixed_nomination_exact']['objective']
 row['certified_domain']=not(row['illegal_decisions']or row['scorer_disagreements']or row['menu_failures']) and min(row['fixed_nomination_search_gap'],row['joint_gap'])>=-1e-9
 row['status']='completed'if row['certified_domain']else'failed_gate';row['elapsed_seconds']=time.perf_counter()-start
 scoring.ScenarioScorer.decision.cache_clear();return row

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--frozen-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 if any(a.out.iterdir()):raise ValueError('Use a new output directory; never overwrite a recorded run')
 # Validate the preregistered implementation before importing/calling frozen TS.
 sys.path.insert(0,str(ROOT/'research/tools'));import registry
 reg=registry.read()['EXP-TS-SEARCH-001'];implementation=reg['implementation'];assert implementation and reg['state']=='running'
 assert implementation['harness_sha256']==digest(__file__)
 manifest=json.loads((S/'inputs/implementation-manifest.json').read_text())
 for path,h in manifest['files'].items():assert digest(ROOT/path)==h,('Implementation/input changed',path)
 original_protocol=digest(ROOT/'research/experiments/EXP-TS-SEARCH-001.json');start=PROCESS_START;result=dict(schema='TS-exact-small-results-v1',experiment_id='EXP-TS-SEARCH-001',protocol_sha256=original_protocol,implementation_sha256=digest(__file__),input_sha256=digest(S/'inputs/instances.json'),source_commit=PIN,command=' '.join(sys.argv),budget_seconds=120,rows=[],attempted=[],not_run=[],status='running',python=sys.version,platform=platform.platform(),numpy=np.__version__,pandas=pd.__version__,initial_registration_event_sha256=implementation['sha256'])
 cases=json.loads((S/'inputs/instances.json').read_text())['cases'];assert len(cases)==42
 def timeout(_s,_f):raise TimeoutError('Original 120-second wall budget exhausted; no automatic extension')
 old=signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,max(.001,120.-(time.perf_counter()-start)))
 try:
  planner,season,scoring,live,config,source=load_frozen(a.frozen_root);result['configuration']=asdict(config)
  for case in cases:
   result['attempted'].append(case['id']);print('START',case['id'],round(time.perf_counter()-start,3),flush=True)
   try:row=run_case(case,planner,season,scoring,live,config)
   except TimeoutError:raise
   except Exception as e:row=dict(id=case['id'],level=case['level'],status='error',error=repr(e),traceback=traceback.format_exc())
   result['rows'].append(row);print('END',case['id'],row['status'],round(time.perf_counter()-start,3),flush=True);write(a.out/'results.json',result)
  result['status']='completed'if all(r['status']=='completed'for r in result['rows'])else'failed_gate'
 except TimeoutError as e:result['status']='blocked_budget';result['failure']=str(e)
 except Exception as e:result['status']='blocked_execution';result['failure']=repr(e);result['traceback']=traceback.format_exc()
 finally:
  signal.setitimer(signal.ITIMER_REAL,0.);signal.signal(signal.SIGALRM,old);result['elapsed_seconds']=time.perf_counter()-start;done={r['id']for r in result['rows']};result['not_run']=[c['id']for c in cases if c['id']not in done];write(a.out/'results.json',result)
 print(json.dumps(dict(status=result['status'],rows=len(result['rows']),not_run=result['not_run'],elapsed_seconds=result['elapsed_seconds'])),flush=True)
if __name__=='__main__':main()
