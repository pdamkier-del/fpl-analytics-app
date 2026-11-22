from pathlib import Path
import copy,gzip,hashlib,importlib.util,json,shutil
import pytest
ROOT=Path(__file__).resolve().parents[3];S=ROOT/'research/stage0';R=ROOT/'research'
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
reg=module('stage0_registry',R/'tools/registry.py');verify=module('stage0_verify',S/'code/verify_sources.py')
def load(p):return json.loads(p.read_text())
def test_original_protocols_and_event_prefix_are_frozen():
 original=load(S/'original-registry.json');assert len(original['protocols'])==25
 for name,h in original['protocols'].items():assert hashlib.sha256((R/'experiments'/name).read_bytes()).hexdigest()==h
 lines=(R/'events.jsonl').read_bytes().splitlines(keepends=True)
 assert hashlib.sha256(b''.join(lines[:original['events_lines']])).hexdigest()==original['events_sha256']

def test_complete_directory_coverage_and_exact_copy_deduplication():
 index=json.loads(gzip.decompress((S/'tree-index.json.gz').read_bytes()));assert len(index)==3169
 keys=[(r['path'],r['git_blob'])for r in index];assert len(keys)==len(set(keys))
 assert all(r['commits']==sorted(set(r['commits']))for r in index)
 dirs={r['path'].split('/')[2]for r in index if r['path'].startswith('analysis/results/')and len(r['path'].split('/'))>3}
 families=load(S/'family-definitions.json');assigned=[d for f in families for d in f['directories']]
 assert len(dirs)==184 and len(assigned)==len(set(assigned))and set(assigned)==dirs
 matrix=json.loads(gzip.decompress((S/'historical-matrix.json.gz').read_bytes()));assert {r['id']for r in matrix}=={f['id']for f in families}
 assert all(r['promotion'].startswith('None;')for r in matrix)

def test_all_imported_records_are_historical_not_new_runs():
 records=reg.read();original=load(S/'original-registry.json');added={k for k in records if k.startswith('LEGACY-')}-{p[:-5]for p in original['protocols']}
 assert added=={f'LEGACY-{i:03}'for i in range(16,54)}
 for id in added:
  r=records[id];assert r['protocol']['kind']=='legacy'and r['implementation']is None
  assert r['protocol']['full_experiment_command']is None and not r['protocol']['execution_ready']
 assert not any(r['state']=='running'for r in records.values()if r['protocol']['kind']=='legacy')

def test_observations_leave_states_protocols_and_implementations_unchanged():
 records=reg.read();observations=[(id,e)for id,r in records.items()for e in r['events']if e['kind']=='evidence_reconciled']
 assert len(observations)==11
 for id,e in observations:
  assert e['state']==records[id]['protocol']['initial_status'];assert not e.get('harness')
  assert all(later['sequence']>e['sequence']for later in records[id]['events']if later['kind']=='implementation_registered')

def test_reconciliation_event_tamper_and_result_tamper_fail_closed(tmp_path):
 root=tmp_path/'research';shutil.copytree(R,root)
 original=(root/'experiments/EXP-TS-SEARCH-001.json').read_bytes();initial_state=reg.read(root)['EXP-TS-SEARCH-001']['state']
 target=root/'stage0/public-test.json';target.write_text('{"synthetic_public":true}')
 reg.append_reconciliation(root,'EXP-TS-SEARCH-001','Synthetic metadata-only evidence',['research/stage0/public-test.json'])
 assert reg.read(root)['EXP-TS-SEARCH-001']['state']==initial_state;assert (root/'experiments/EXP-TS-SEARCH-001.json').read_bytes()==original
 target.write_text('{"synthetic_public":false}')
 with pytest.raises(ValueError,match='Reconciliation evidence changed'):reg.read(root)

def test_reconciliation_cannot_be_used_to_promote_state(tmp_path):
 root=tmp_path/'research';shutil.copytree(R,root);path=root/'events.jsonl';lines=path.read_text().splitlines();last=max(i for i,line in enumerate(lines)if json.loads(line)['kind']=='evidence_reconciled');lines=lines[:last+1];e=json.loads(lines[-1]);assert e['kind']=='evidence_reconciled';e['state']='accepted';e.pop('sha256');e['sha256']=reg.digest(reg.canonical(e));lines[-1]=json.dumps(e);path.write_text('\n'.join(lines)+'\n')
 with pytest.raises(ValueError,match='preserve state'):reg.read(root)

def test_result_archive_hashes_and_old_arithmetic_without_model_execution():
 r=verify.verify();assert r['primary_artifacts_verified']==225 and r['selected_source_copies_verified']==21
 assert r['old_TS_cases']['count']==6 and r['old_TS_cases']['max_recorded_transfer_utility_gap']==0
 assert r['old_TS_cases']['max_recorded_XI_gap']==pytest.approx(.18)
 assert not r['fit_executed']and not r['simulation_executed']and not r['TS_search_executed']


def test_matrix_sources_and_existing_result_paths_resolve():
 matrix=json.loads(gzip.decompress((S/'historical-matrix.json.gz').read_bytes()));bundle=json.loads(gzip.decompress((S/'primary-evidence.json.gz').read_bytes()))
 for family in matrix:
  for source in family['configuration']['sources']:
   actual=bundle[source['array_index']];assert actual['git_blob']==source['git_blob']and actual['sha256']==source['sha256']
  for path in family['configuration']['existing_sources']:assert (ROOT/path).is_file()


def test_no_private_manager_refs_or_new_trial_gates():
 import re
 refs=load(S/'source-refs.json');assert refs['private_manager_specific_branches_excluded']==1
 assert not any(re.search(r'(manager|entry)[-_]\d{4,}',b['name'],re.I)for b in refs['branches'])
 p=reg.read()['EXP-MM-SUB-20261108']['protocol'];assert p['sample_size']['minimum_gws']==8 and p['sample_size']['minimum_matches']==80
 receipt=load(S/'evidence/substitution-status-observed-20261122.json');assert receipt['evaluation']['completed_gws']==0 and receipt['evaluation']['completed_matches']==0
 assert all(not json.loads(line).get('independent_validation')for line in(R/'events.jsonl').read_text().splitlines())
