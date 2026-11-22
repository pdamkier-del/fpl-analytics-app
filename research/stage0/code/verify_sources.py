"""Read-only reconciliation of archived evidence. No models, fits or search run.

Offline: python research/stage0/code/verify_sources.py
Full Git provenance: python research/stage0/code/verify_sources.py --source-git /path/to/repo
"""
import argparse,csv,gzip,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];S=ROOT/'research/stage0'
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(p.read_text())
def batch_blobs(repo,oids):
 oids=sorted(set(oids));raw=subprocess.check_output(['git','-C',str(repo),'cat-file','--batch'],input=('\n'.join(oids)+'\n').encode());out={};pos=0
 for oid in oids:
  end=raw.index(b'\n',pos);head=raw[pos:end].decode().split();assert len(head)==3 and head[1]=='blob',head
  size=int(head[2]);start=end+1;blob=raw[start:start+size];assert hashlib.sha1(b'blob '+str(size).encode()+b'\0'+blob).hexdigest()==oid
  out[oid]=blob;pos=start+size+1
 assert pos==len(raw);return out

def verify(repo=None):
 report={'scope':'Evidence bytes, original receipt arithmetic and inventory only; no model reruns, no new efficacy tests','fit_executed':False,'simulation_executed':False,'TS_search_executed':False}
 original=load(S/'original-registry.json')
 for name,h in original['protocols'].items():assert sha((ROOT/'research/experiments'/name).read_bytes())==h
 lines=(ROOT/'research/events.jsonl').read_bytes().splitlines(keepends=True)
 assert sha(b''.join(lines[:original['events_lines']]))==original['events_sha256']
 report['original_protocols_unchanged']=len(original['protocols']);report['original_events_prefix_unchanged']=True
 bundle=json.loads(gzip.decompress((S/'primary-evidence.json.gz').read_bytes()))
 for r in bundle:
  b=r['text'].encode();assert sha(b)==r['sha256'];assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==r['git_blob']
 receipts=load(S/'source-receipts.json')
 for r in receipts:assert sha((ROOT/r['local_path']).read_bytes())==r['sha256']
 report.update(primary_artifacts_verified=len(bundle),selected_source_copies_verified=len(receipts))
 index=json.loads(gzip.decompress((S/'tree-index.json.gz').read_bytes()))
 dirs={r['path'].split('/')[2] for r in index if r['path'].startswith('analysis/results/') and len(r['path'].split('/'))>3}
 families=load(S/'family-definitions.json');assigned=[d for f in families for d in f['directories']]
 assert len(assigned)==len(set(assigned)) and set(assigned)==dirs
 report.update(result_directories_assigned=len(dirs),historical_families=len(families),unassigned_result_directories=[])
 # Exact arithmetic against archived public model-constructed cases, not a new optimizer run.
 ts=next(r for r in receipts if r['path'].endswith('/historical-TS-cases.json'));cases=load(ROOT/ts['local_path'])
 for c in cases:
  assert abs(c['utility_regret']-(c['exact']['utility']-c['fast']['utility']))<1e-12
  assert abs(c['XI_gain']-(c['exact_XI']['score']-c['heuristic_XI_score']))<1e-12
 report['old_TS_cases']={'count':len(cases),'horizons':sorted({c['horizon'] for c in cases}),'max_recorded_transfer_utility_gap':max(c['utility_regret'] for c in cases),'max_recorded_XI_gap':max(c['XI_gain'] for c in cases),'arithmetic_matches':True,'scoring_limit':'Transfer enumeration still calls heuristic s.decision per squad; exhaustive nomination is only separately applied to unchanged squad; buffer1.5 vs current1.0.'}
 gate=next(r for r in receipts if r['path'].endswith('/assist-decision.json'));j=load(ROOT/gate['local_path'])
 diffs=[]
 for m in j['metrics']:
  diffs.append(dict(season=m['season'],group=m['group'],xp_MAE_delta=m['xp_MAE_after']-m['xp_MAE_before'],assist_Brier_delta=m['assist_Brier_after']-m['assist_Brier_before']))
 report['archived_assist_gate']={'accepted_in_original_gate':j['accepted'],'no_independent_accuracy_claim':j['no_independent_accuracy_claim'],'paired_FWD_assist_Brier_delta95':j['paired_FWD_assist_Brier_delta95'],'differences_recomputed_from_summary':diffs}
 # The conditional reserve counterexample is an exact identity from the archived derivation.
 old_first=1-.5*(1-.5)+.5*(1-.1);old_second=1-.5*(1-.5)+.5*(1-.9)
 assert abs(old_first-1.2)<1e-12 and abs(old_second-.8)<1e-12
 report['keeper_reserve_identity']={'old':[old_first,old_second],'conditional_correct':[1.,1.],'scope':'Artificial fixed-interval expectation only; not historical accuracy or new simulator test'}
 if repo:
  inventory=load(ROOT/'analysis/audits/2026-11-22/research-inventory.json');tree=subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','fd3907f4','--','analysis/results'],text=True)
  paths={line.split('\t',1)[1]:line.split()[2] for line in tree.splitlines()};requested=[f for s in inventory for f in s['files']];found={f['path']:paths.get('analysis/results/'+f['path']) for f in requested}
  blobs=batch_blobs(repo,[b for b in found.values() if b]);missing=[];mismatch=[]
  for f in requested:
   oid=found[f['path']]
   if oid is None:missing.append(f['path'])
   elif sha(blobs[oid])!=f['sha256']:mismatch.append(f['path'])
  report['PR41_inventory']={'groups':len(inventory),'files':len(requested),'hash_matches':len(requested)-len(missing)-len(mismatch),'not_in_pinned_git_tree':missing,'hash_mismatches':mismatch,'scope':'Full archived inventory compared to fd3907f4; mismatch is reported, not silently repaired'}
  tests=list(csv.DictReader((ROOT/'analysis/audits/2026-11-22/test-inventory.csv').open()));missing_tests=[]
  for t in tests:
   if subprocess.run(['git','-C',str(repo),'cat-file','-e',t['source_commit']+':'+t['path']],capture_output=True).returncode:missing_tests.append(t['path'])
  report['original_test_inventory']={'listed':len(tests),'source_paths_exist':len(tests)-len(missing_tests),'missing':missing_tests,'executed':False}
  # Verify every unique path/blob association against the pinned public commit tree.
  bycommit={}
  for r in index:
   for commit in r['commits']:bycommit.setdefault(commit,[]).append(r)
  for commit,entries in bycommit.items():
   tree=subprocess.check_output(['git','-C',str(repo),'ls-tree','-r',commit],text=True);mapping={s.split('\t',1)[1]:s.split()[2] for s in tree.splitlines()}
   assert all(mapping.get(r['path'])==r['git_blob'] for r in entries)
  report['public_ref_trees_verified']=len(bycommit)
 else:report['git_verification']='Not requested; use --source-git for full pinned inventory/tree/test-source checks'
 return report

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-git',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();r=verify(a.source_git);text=json.dumps(r,indent=2)+'\n'
 if a.output:a.output.write_text(text)
 print(text)
if __name__=='__main__':main()
