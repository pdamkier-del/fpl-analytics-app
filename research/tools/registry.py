"""Offline research registry: immutable registrations and append-only public state events."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];R=ROOT/'research'
TRANSITIONS={'proposed':{'ready','awaiting_data','rejected'},'ready':{'running','awaiting_data','rejected'},'running':{'completed','awaiting_data'},'awaiting_data':{'ready','rejected'},'completed':{'accepted','rejected'},'accepted':set(),'rejected':set()}
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def digest(x):return hashlib.sha256(x).hexdigest()
def read(root=R):
 root=Path(root);schema=json.loads((root/'registry-schema.json').read_text());records={}
 for p in sorted((root/'experiments').glob('*.json')):
  v=json.loads(p.read_text())
  if v['id']in records or p.stem!=v['id']:raise ValueError('Duplicate or misnamed experiment')
  if any(k not in v for k in schema['required_fields']):raise ValueError('Required protocol field missing')
  if v['initial_status']not in schema['states']:raise ValueError('Unknown state')
  records[v['id']]={'protocol':v,'sha256':digest(p.read_bytes()),'state':v['initial_status'],'events':[],'implementation':None}
 previous=None;registered=set()
 for i,line in enumerate((root/'events.jsonl').read_text().splitlines(),1):
  e=json.loads(line);h=e.pop('sha256')
  if e['sequence']!=i or e['previous']!=previous or digest(canonical(e))!=h:raise ValueError('Event chain mismatch')
  v=records[e['experiment_id']]
  if e['protocol_sha256']!=v['sha256']:raise ValueError('Registered protocol was overwritten')
  if e['kind']=='registered':
   if e['experiment_id']in registered or e['state']!=v['state']:raise ValueError('Duplicate or inconsistent registration')
   registered.add(e['experiment_id'])
  elif e['kind']=='implementation_registered':
   if e['experiment_id']not in registered or v['state']not in ['proposed','ready','awaiting_data']or not e.get('command')or not e.get('harness_sha256'):raise ValueError('Invalid implementation registration')
   v['implementation']=e
  elif e['kind']=='evidence_reconciled':
   if e['experiment_id']not in registered or e['state']!=v['state']or not e.get('reason')or not e.get('evidence'):raise ValueError('Reconciliation must preserve state and cite evidence')
   for item in e['evidence']:
    path=(root.parent/item['path']).resolve()
    if not path.is_relative_to(root.parent.resolve())or not path.is_file()or digest(path.read_bytes())!=item['sha256']:raise ValueError('Reconciliation evidence changed or disappeared')
  elif e['kind']=='state_changed':
   if e['experiment_id']not in registered or e['state']not in TRANSITIONS[v['state']]:raise ValueError('Illegal state transition')
   if e['state']=='running'and v['implementation']is None:raise ValueError('Execution harness not registered')
   if not e.get('evidence')or not e.get('reason'):raise ValueError('State change requires public evidence and reason')
   if e['state']=='accepted'and not e.get('independent_validation'):raise ValueError('Acceptance needs explicit independent validation statement')
   for item in e['evidence']:
    path=(root.parent/item['path']).resolve()
    if not path.is_relative_to(root.parent.resolve())or not path.is_file()or digest(path.read_bytes())!=item['sha256']:raise ValueError('Recorded result evidence changed or disappeared')
   v['state']=e['state']
  else:raise ValueError('Unknown registry event')
  e['sha256']=h;v['events'].append(e);previous=h
 if registered!=set(records):raise ValueError('Unregistered protocol')
 for v in records.values():
  if v['implementation']is not None:
   item=v['implementation'];path=(root.parent/item['harness']).resolve()
   if not path.is_relative_to(root.parent.resolve())or not path.is_file()or digest(path.read_bytes())!=item['harness_sha256']:raise ValueError('Registered execution harness changed')
  if any(d not in records for d in v['protocol']['dependencies']):raise ValueError('Unknown dependency')
 def visit(k,stack):
  if k in stack:raise ValueError('Dependency cycle')
  for d in records[k]['protocol']['dependencies']:visit(d,stack|{k})
 for k in records:visit(k,set())
 return records

def evidence(id,root=R,repository=ROOT):
 records=read(root);v=records[id]['protocol'];hashes=json.loads((Path(root)/'evidence/source-hashes.json').read_text());result=[]
 for link in v['result_links']:
  if link.startswith('https://'):result.append({'source':link,'verification':'external link; not fetched or independently reverified'});continue
  p=(Path(repository)/link).resolve()
  if not p.is_relative_to(Path(repository).resolve())or not p.is_file():raise ValueError('Evidence path invalid or missing')
  if link not in hashes or digest(p.read_bytes())!=hashes[link]:raise ValueError('Original evidence changed')
  result.append({'source':link,'sha256':hashes[link],'verification':'original local evidence hash verified'})
 return result

def validate(root=R,repository=ROOT):
 records=read(root)
 for id in records:evidence(id,root,repository)
 protected=records.get('EXP-MM-SUB-20261108')
 if not protected or not protected['protocol'].get('protected_external_protocol'):raise ValueError('Existing substitution protection missing')
 p=Path(repository)/'analysis/audits/2026-11-22/evidence/fpl-joint-substitution/prospective-plan.json';q=json.loads(p.read_text());s=protected['protocol']['sample_size']
 if s['minimum_gws']!=q['minimum_prospective_completed_gws']or s['minimum_matches']!=q['minimum_prospective_matches']:raise ValueError('Existing trial gate changed')
 return {'experiments':len(records),'states':{s:sum(v['state']==s for v in records.values())for s in TRANSITIONS},'existing_protocol_unchanged':True}

def table(root=R):
 records=read(root);lines=['# FPL Research Lab — research status','', 'Snapshot including Phase4 setup, 23 November 2026. Generated from registry; not a live job monitor.','', '| Experiment | State | Priority | Execution-ready | Next action |','| --- | --- | --- | --- | --- |']
 for id,v in sorted(records.items(),key=lambda x:x[1]['protocol']['priority']):
  p=v['protocol'];finished=v['state']=='completed'and v['implementation']is not None
  action='Read completion evidence in append-only events and SESSION_HANDOFF; original protocol remains unchanged.'if finished else p['next_action']
  execution='completed; no model promotion'if finished else('harness registered; check data gates'if v['implementation']is not None else'no; see prerequisites/implementation')
  lines.append(f"| [{id}](experiments/{id}.json) | {v['state']} | {p['priority']} | {execution} | {action.replace('|','/')} |")
 ready_ids=[key for key,item in sorted(records.items(),key=lambda pair:pair[1]['protocol']['priority'])if item['state']=='ready'and item['protocol']['kind']!='legacy']
 next_ready=ready_ids[0]if ready_ids else'none'
 lines+=['','`ready` means scientific/data prerequisites support starting implementation. It does not claim the execution harness exists. `awaiting_data` is not a failed model. Historical accepted/rejected decisions have the narrow scope in their evidence.','', f'Stage 0 inventory review remains pending. Completed research: TS-search in results/EXP-TS-SEARCH-001/REPORT.md; PM definitions in results/EXP-PM-DEFS-001/REPORT.md; isolated TS funding comparison in results/EXP-TS-FUNDING-001/REPORT.md (practical two-family gate failed; no promotion). Next existing ready registration: {next_ready}; check SESSION_HANDOFF for ownership and remaining gates. Prospective MM/PM setup: results/EXP-MM-PM-LIVE-SETUP/REPORT.md; code/archive link verified, awaiting eligible originals/final outcomes and reviewed report-workflow integration. No model promotion; protected substitution trial unchanged.','', 'Never count seen GW8–10 again as new validation. New MM/PM holdouts begin at an eligible later origin, not after reviewing current GW11 outcomes.','']
 return '\n'.join(lines)

def append_state(root,id,status,reason,links,independent=False):
 root=Path(root);records=read(root);v=records[id]
 if status not in TRANSITIONS[v['state']]:raise ValueError('Illegal state transition')
 if status=='running'and v['implementation']is None:raise ValueError('Execution harness not registered')
 if not reason or not links:raise ValueError('Reason and immutable public evidence required')
 if status=='accepted'and not independent:raise ValueError('Accepted requires independent validation statement; production is still unchanged')
 verified=[]
 for link in links:
  path=(root.parent/link).resolve()
  if not path.is_relative_to(root.parent.resolve())or not path.is_file():raise ValueError('State evidence must be an existing public repository file')
  if not str(path.relative_to(root.parent.resolve())).startswith(('research/results/','research/evidence/','analysis/audits/','analysis/followup-')):raise ValueError('State evidence outside public evidence namespaces')
  verified.append({'path':link,'sha256':digest(path.read_bytes())})
 lines=(root/'events.jsonl').read_text().splitlines();last=json.loads(lines[-1]);e={'sequence':len(lines)+1,'event_id':'STATE-'+str(len(lines)+1),'kind':'state_changed','experiment_id':id,'at':datetime.now(timezone.utc).isoformat(),'state':status,'protocol_sha256':v['sha256'],'reason':reason,'evidence':verified,'independent_validation':independent,'previous':last['sha256']};e['sha256']=digest(canonical(e))
 with(root/'events.jsonl').open('a')as h:h.write(json.dumps(e,sort_keys=True,ensure_ascii=False)+'\n')
 return e

def append_reconciliation(root,id,reason,links):
 """Append evidence without changing the registered protocol, state or implementation."""
 root=Path(root);v=read(root)[id]
 if not reason or not links:raise ValueError('Reason and immutable public evidence required')
 verified=[]
 for link in links:
  path=(root.parent/link).resolve()
  if not path.is_relative_to(root.parent.resolve())or not path.is_file()or not str(path.relative_to(root.parent.resolve())).startswith(('research/stage0/','research/evidence/')):raise ValueError('Invalid public reconciliation evidence')
  verified.append({'path':link,'sha256':digest(path.read_bytes())})
 lines=(root/'events.jsonl').read_text().splitlines();last=json.loads(lines[-1]);e={'sequence':len(lines)+1,'event_id':'RECON-'+str(len(lines)+1),'kind':'evidence_reconciled','experiment_id':id,'at':datetime.now(timezone.utc).isoformat(),'state':v['state'],'protocol_sha256':v['sha256'],'reason':reason,'evidence':verified,'previous':last['sha256']};e['sha256']=digest(canonical(e))
 with(root/'events.jsonl').open('a')as h:h.write(json.dumps(e,sort_keys=True,ensure_ascii=False)+'\n')
 return e

def register_implementation(root,id,command,harness,repository=ROOT):
 root=Path(root);records=read(root);v=records[id];path=(Path(repository)/harness).resolve()
 if v['state']not in ['proposed','ready','awaiting_data']or not command or not path.is_relative_to(Path(repository).resolve())or not path.is_file():raise ValueError('Implementation must be a real versioned repository file before running')
 lines=(root/'events.jsonl').read_text().splitlines();last=json.loads(lines[-1]);e={'sequence':len(lines)+1,'event_id':'IMPL-'+str(len(lines)+1),'kind':'implementation_registered','experiment_id':id,'at':datetime.now(timezone.utc).isoformat(),'state':v['state'],'protocol_sha256':v['sha256'],'command':command,'harness':harness,'harness_sha256':digest(path.read_bytes()),'previous':last['sha256']};e['sha256']=digest(canonical(e))
 with(root/'events.jsonl').open('a')as h:h.write(json.dumps(e,sort_keys=True,ensure_ascii=False)+'\n')
 return e

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['validate','status','next','show','search','evidence','record','implement','reconcile']);p.add_argument('id',nargs='?');p.add_argument('--verify',action='store_true');p.add_argument('--render',action='store_true');p.add_argument('--command');p.add_argument('--harness');p.add_argument('--state',choices=list(TRANSITIONS));p.add_argument('--reason');p.add_argument('--evidence',action='append');p.add_argument('--independent-validation',action='store_true');a=p.parse_args();records=read()
 if a.action=='validate':print(json.dumps(validate(),indent=2))
 elif a.action=='status':
  s=table()
  if a.render:(R/'STATUS.md').write_text(s)
  print(s)
 elif a.action=='next':
  rows=sorted((v for v in records.values()if v['state']=='ready'and v['protocol']['kind']!='legacy'),key=lambda v:v['protocol']['priority']);print(json.dumps({'next':rows[0]['protocol']if rows else None,'implementation':rows[0]['implementation']if rows else None,'note':'Read SESSION_HANDOFF; ready is not the same as an implemented execution harness.'},indent=2))
 elif a.action=='search':print(json.dumps([v['protocol']for v in records.values()if(a.id or'').lower()in json.dumps(v['protocol']).lower()],indent=2))
 elif a.action=='show':print(json.dumps(records[a.id],indent=2))
 elif a.action=='evidence':print(json.dumps(evidence(a.id),indent=2))
 elif a.action=='implement':print(json.dumps(register_implementation(R,a.id,a.command,a.harness),indent=2))
 elif a.action=='reconcile':print(json.dumps(append_reconciliation(R,a.id,a.reason,a.evidence),indent=2))
 elif a.action=='record':print(json.dumps(append_state(R,a.id,a.state,a.reason,a.evidence,a.independent_validation),indent=2))
if __name__=='__main__':
 try:main()
 except (KeyError,ValueError,OSError)as e:print('Registry validation failed: '+str(e),file=sys.stderr);sys.exit(1)
