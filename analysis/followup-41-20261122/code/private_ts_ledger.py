"""Standalone private TS decision logger. No model calls, uploads, public export or backdating CLI."""
from __future__ import annotations
import argparse,collections,fcntl,gzip,hashlib,json,math,os,secrets,sys,subprocess
from datetime import datetime,timezone,timedelta
from pathlib import Path

def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def clock(s):
 try:d=datetime.fromisoformat(s.replace('Z','+00:00'))
 except (TypeError,ValueError,AttributeError):raise ValueError('Missing or invalid timestamp')from None
 if d.tzinfo is None:raise ValueError('Timestamp requires timezone')
 return d.astimezone(timezone.utc)
def integer(x,low,high):return type(x)is int and low<=x<=high
def require(ok,why):
 if not ok:raise ValueError(why)
def legal_squad(ids,catalog):
 require(len(ids)==15 and len(set(ids))==15 and all(i in catalog for i in ids),'Illegal or unknown squad')
 require(collections.Counter(catalog[i]['position']for i in ids)=={1:2,2:5,3:5,4:3},'Squad positions invalid')
 require(max(collections.Counter(catalog[i]['team_id']for i in ids).values())<=3,'Club limit exceeded')
def lineup(rows,catalog):
 require(isinstance(rows,list),'Missing nomination');ids=[r.get('id')for r in rows];legal_squad(ids,catalog)
 roles=[r.get('role')for r in rows];require(collections.Counter(roles)=={'C':1,'VC':1,'XI':9,'BGK':1,'B1':1,'B2':1,'B3':1},'Captain/vice/bench roles invalid')
 xi=[r['id']for r in rows if r['role']in ['C','VC','XI']];n=collections.Counter(catalog[i]['position']for i in xi)
 require(n[1]==1 and 3<=n[2]<=5 and 2<=n[3]<=5 and 1<=n[4]<=3,'XI formation invalid')
 require(catalog[next(r['id']for r in rows if r['role']=='BGK')]['position']==1,'Keeper bench invalid')
 return ids

def validate_intention(f,state,plan,decision,now):
 require(now<clock(f.get('origin_deadline')),'Intention must be before deadline')
 catalog={p['id']:p for p in f['players']};owned=state['squad'];chips=state['chips_used'];gw=f['gws'][0];recommended=lineup(plan.get('lineup'),catalog)
 chosen=lineup(decision.get('rows'),catalog)
 require(decision.get('source')and clock(decision.get('observed_at'))<=now,'Decision source/time missing')
 require(decision.get('semantics')=='intended_predeadline_not_verified_execution','Decision execution must not be invented')
 require(decision.get('choice')in ['keep_squad','follow_plan','custom'],'Decision choice missing')
 before={p['id']for p in owned};after=set(chosen)
 if decision['choice']=='keep_squad':require(after==before,'Keep decision changed squad')
 if decision['choice']=='follow_plan':require(after==set(recommended),'Follow-plan decision differs from recommendation')
 require(set(decision.get('incoming',[]))==after-before and set(decision.get('outgoing',[]))==before-after,'Decision transfers do not reconcile')
 active=decision.get('active_chip');require(active in [None,*chips],'Unknown active chip')
 if active:require(not any((x<=19)==(gw<=19)for x in chips[active]),'Active chip unavailable in this half')
 return {k:decision[k]for k in ['source','observed_at','semantics','choice','rows','incoming','outgoing','active_chip']}

def validate(f,state,plan,decision,now):
 require(now.tzinfo is not None,'Clock requires timezone')
 require(f.get('forecast_sha256')==sha(canonical({k:v for k,v in f.items()if k!='forecast_sha256'})),'Forecast content hash mismatch')
 gws=f.get('gws');require(isinstance(gws,list)and gws and integer(gws[0],1,38),'Missing origin GW');gw=gws[0]
 require(gws==list(range(gw,min(39,gw+6))),'Complete six-GW horizon required (season-end truncated only)')
 deadline=clock(f.get('origin_deadline'));asof=clock(f.get('data_asof'));require(asof<=now<deadline,'Capture must be before origin deadline and after source cutoff')
 limit=f.get('freshness_limit_hours',24);require(isinstance(limit,(float,int))and 0<limit<=24 and now-asof<=timedelta(hours=limit),'Forecast stale')
 catalog={p['id']:p for p in f.get('players',[])};require(len(catalog)==len(f.get('players',[]))and bool(catalog),'Forecast identities invalid')
 for p in catalog.values():
  weeks=p.get('weeks',[]);require(sorted(w['gw']for w in weeks)==gws,'Player horizon incomplete or duplicated')
  require(all(isinstance(w.get('xpts'),(int,float))and math.isfinite(w['xpts'])for w in weeks),'Forecast xP missing')
 require(state.get('season')==f.get('season')and state.get('gw')==gw,'Manager season/GW mismatch')
 require(bool(state.get('source'))and clock(state.get('observed_at'))<=now,'Manager source/time invalid')
 require(integer(state.get('free_transfers'),0,5)and integer(state.get('bank_tenths'),0,1000),'FT or bank missing')
 owned=state.get('squad',[]);legal_squad([p.get('id')for p in owned],catalog);require(all(integer(p.get('purchase_price_tenths'),1,1000)for p in owned),'Purchase prices required')
 chips=state.get('chips_used');require(isinstance(chips,dict)and set(chips)=={'wildcard','free_hit','bench_boost','triple_captain'},'Complete chip histories required')
 for history in chips.values():
  require(isinstance(history,list)and all(integer(x,1,gw-1)for x in history)and len(history)==len(set(history)),'Chip history invalid')
  require(sum(x<=19 for x in history)<=1 and sum(x>=20 for x in history)<=1,'Chip reused in same half')
 require(plan.get('forecast_sha256')==f['forecast_sha256']and plan.get('gw')==gw and plan.get('ts_ran')is True,'Plan not linked to forecast')
 require(plan.get('manager_state_sha256')==sha(canonical(state)),'Plan not linked to exact manager state')
 computed=clock(plan['computed_at'])if plan.get('computed_at')else now
 require(asof<=computed<=now and clock(state['observed_at'])<=computed,'Plan/source/manager clocks inconsistent')
 path=plan.get('plan',{}).get('path',[]);require([r.get('gw')for r in path]==gws,'Plan horizon incomplete')
 keep=plan.get('comparison',{}).get('hold_squad_without_transfers',[])
 require([r.get('gw')for r in keep]==gws and all(isinstance(r.get('expected_score'),(float,int))and math.isfinite(r['expected_score'])for r in keep),'Keep-squad control missing or incomplete')
 weights=plan.get('plan',{}).get('weights');require(weights==[1.,.6,.36,.216,.1296,.07776][:len(gws)]or tuple(weights or [])==(1.,.6,.36,.216,.1296,.07776)[:len(gws)],'Unexpected TS weights')
 recommended=lineup(plan.get('lineup'),catalog)
 if decision is not None:validate_intention(f,state,plan,decision,now)
 # No secret-bearing arbitrary objects are copied into the archive.
 sanitized_state={k:state[k]for k in ['season','gw','source','observed_at','bank_tenths','free_transfers','chips_used']}
 sanitized_state['squad']=[{k:r[k]for k in ['id','purchase_price_tenths']}for r in owned]
 sanitized_plan={k:plan[k]for k in ['ts_ran','gw','forecast_sha256','manager_state_sha256','computed_at','plan','lineup','comparison','chips_ran','chips_status','chip_assessment','chip_plan']if k in plan}
 sanitized_decision={k:decision[k]for k in ['source','observed_at','semantics','choice','rows','incoming','outgoing','active_chip']}if decision is not None else None
 return {'schema':'fpl-private-ts-capture-v1','issued_at':now.isoformat(),'deadline':deadline.isoformat(),'clock_proof':'local_system_clock_only_not_independent_timestamp','gw':gw,'horizon_gws':gws,'forecast_sha256':f['forecast_sha256'],'manager_state_sha256':plan['manager_state_sha256'],'forecast':f,'manager_state':sanitized_state,'recommendation':sanitized_plan,'manager_decision':sanitized_decision,'executed_transfers':None,'capture_kind':'recommendation_with_intent'if decision is not None else 'recommendation_only','control_scope':'Existing planner keep-squad expected scores; no hindsight optimization; no re-solving performed'}

def private_root(path):
 path=Path(path).expanduser().resolve()
 existing=next(p for p in [path,*path.parents]if p.is_dir())
 probe=subprocess.run(['git','-C',str(existing),'rev-parse','--show-toplevel'],capture_output=True)
 require(probe.returncode!=0,'Private ledger must be outside every Git worktree')
 path.mkdir(mode=0o700,parents=True,exist_ok=True);os.chmod(path,0o700);return path

def verify(root):
 root=Path(root);index=root/'ledger.jsonl';previous=None;count=0;last=None;listed=set()
 if not index.exists():
  require(not list(root.glob('record-*.json.gz')),'Unindexed private record; manual recovery required')
  return 0
 for line in index.read_text().splitlines():
  e=json.loads(line);listed.add(e['record']);digest=e.pop('entry_sha256');require(digest==sha(canonical(e))and e['previous']==previous,'Ledger chain mismatch');require(e['sequence']==count+1,'Sequence mismatch')
  require(Path(e['record']).name==e['record'],'Invalid record path');raw=(root/e['record']).read_bytes();require(sha(raw)==e['record_sha256'],'Private record hash mismatch');record=json.loads(gzip.decompress(raw));issued=clock(record['issued_at']);require(issued<clock(record['deadline'])and(last is None or issued>=last),'Invalid issue clock')
  require(record['forecast_sha256']==e['forecast_sha256'],'Record/source mismatch');previous=digest;count+=1;last=issued
 require(listed=={p.name for p in root.glob('record-*.json.gz')},'Unindexed private record; manual recovery required')
 return count

def capture(root,f,state,plan,decision=None,*,now=None):
 now=now or datetime.now(timezone.utc);record=validate(f,state,plan,decision,now);root=private_root(root);lock=os.open(root/'.lock',os.O_CREAT|os.O_RDWR,0o600)
 try:
  fcntl.flock(lock,fcntl.LOCK_EX);n=verify(root);index=root/'ledger.jsonl';prior=json.loads(index.read_text().splitlines()[-1])if n else None
  if prior:require(clock(prior['issued_at'])<=now,'Clock moved backwards')
  # Random nonce inside the private payload prevents deterministic fingerprinting of a small manager state.
  record['private_nonce']=secrets.token_hex(32);raw=gzip.compress(canonical(record),mtime=0);name=f'record-{n+1:06d}-{secrets.token_hex(8)}.json.gz';fd=os.open(root/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  with os.fdopen(fd,'wb')as h:h.write(raw);h.flush();os.fsync(h.fileno())
  e={'sequence':n+1,'issued_at':now.isoformat(),'record':name,'record_sha256':sha(raw),'forecast_sha256':f['forecast_sha256'],'previous':prior['entry_sha256']if prior else None};e['entry_sha256']=sha(canonical(e));fd=os.open(index,os.O_CREAT|os.O_APPEND|os.O_WRONLY,0o600)
  with os.fdopen(fd,'ab')as h:h.write(canonical(e)+b'\n');h.flush();os.fsync(h.fileno())
  return {'status':'recorded_private','records':n+1,'capture_id':e['entry_sha256'],'independent_timestamp':False}
 finally:fcntl.flock(lock,fcntl.LOCK_UN);os.close(lock)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['init','capture','verify']);p.add_argument('--root',type=Path,required=True)
 for name in ['forecast','state','plan','decision']:p.add_argument('--'+name,type=Path)
 a=p.parse_args()
 try:
  if a.action=='init':private_root(a.root);out={'status':'private_ledger_ready','records':verify(a.root)}
  elif a.action=='verify':out={'status':'verified_private','records':verify(private_root(a.root))}
  else:
   require(all(getattr(a,k)is not None for k in ['forecast','state','plan','decision']),'Four explicit input files required')
   out=capture(a.root,*(json.loads(getattr(a,k).read_text())for k in ['forecast','state','plan','decision']))
  print(json.dumps(out))
 except Exception:
  # Paths, player IDs, manager IDs and payload values must never enter console/CI logs.
  print(json.dumps({'status':'rejected','reason':'Private capture validation failed; no payload exported'}));return 1
 return 0
if __name__=='__main__':sys.exit(main())
