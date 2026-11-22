from pathlib import Path
import importlib.util,json,shutil,hashlib,re,subprocess
import pytest
ROOT=Path(__file__).resolve().parents[2];R=ROOT/'research';spec=importlib.util.spec_from_file_location('registry',R/'tools/registry.py');reg=importlib.util.module_from_spec(spec);spec.loader.exec_module(reg)
@pytest.fixture
def temporary(tmp_path):
 root=tmp_path/'repo/research';shutil.copytree(R,root);return root

def reseal_synthetic_initial_registry(root):
 previous=None;rows=[]
 for i,p in enumerate(sorted((root/'experiments').glob('*.json')),1):
  j=json.loads(p.read_text());e={'sequence':i,'event_id':str(i),'kind':'registered','experiment_id':j['id'],'at':'synthetic','state':j['initial_status'],'protocol_sha256':reg.digest(p.read_bytes()),'previous':previous};e['sha256']=reg.digest(reg.canonical(e));previous=e['sha256'];rows.append(e)
 (root/'events.jsonl').write_text(''.join(json.dumps(e)+'\n'for e in rows))

def test_all_evidence_and_protected_protocol_validate():
 r=reg.validate();assert r['experiments']==25 and r['existing_protocol_unchanged'];p=reg.read()['EXP-MM-SUB-20261108']['protocol'];assert p['sample_size']['minimum_gws']==8 and p['sample_size']['minimum_matches']==80

def test_registered_protocol_cannot_be_silently_edited(temporary):
 p=temporary/'experiments/EXP-TS-SEARCH-001.json';j=json.loads(p.read_text());j['question']='edited';p.write_text(json.dumps(j))
 with pytest.raises(ValueError,match='overwritten'):reg.read(temporary)

def test_event_tampering_detected(temporary):
 p=temporary/'events.jsonl';p.write_text(p.read_text().replace('"state": "ready"','"state": "accepted"',1))
 with pytest.raises(ValueError,match='chain'):reg.read(temporary)

def test_duplicate_id_detected(temporary):
 p=temporary/'experiments/EXP-TS-SEARCH-001.json';(p.parent/'another.json').write_bytes(p.read_bytes())
 with pytest.raises(ValueError,match='misnamed|Duplicate'):reg.read(temporary)

def test_cycle_detected_on_new_synthetic_registry(temporary):
 ids=['EXP-TS-SEARCH-001','EXP-PM-DEFS-001']
 for i,id in enumerate(ids):
  p=temporary/'experiments'/(id+'.json');j=json.loads(p.read_text());j['dependencies']=[ids[1-i]];p.write_text(json.dumps(j))
 reseal_synthetic_initial_registry(temporary)
 with pytest.raises(ValueError,match='cycle'):reg.read(temporary)

def test_no_direct_acceptance_or_unimplemented_execution(temporary):
 with pytest.raises(ValueError,match='transition'):reg.append_state(temporary,'EXP-TS-SEARCH-001','accepted','no evidence',[])
 with pytest.raises(ValueError,match='harness'):reg.append_state(temporary,'EXP-TS-SEARCH-001','running','not implemented',['research/results/x.json'])
 with pytest.raises(ValueError,match='real versioned'):reg.register_implementation(temporary,'EXP-TS-SEARCH-001','python missing.py','missing.py',temporary.parent)

def test_implementation_and_state_history_append_without_overwriting_protocol(temporary):
 id='EXP-TS-SEARCH-001';p=temporary/'experiments'/(id+'.json');original=p.read_bytes();h=temporary/'tools/synthetic_harness.py';h.write_text('# synthetic registry metadata test; no execution\n');result=temporary/'results/proof.json';result.write_text('{"synthetic_public_test":true}')
 reg.register_implementation(temporary,id,'python research/tools/synthetic_harness.py','research/tools/synthetic_harness.py',temporary.parent)
 reg.append_state(temporary,id,'running','synthetic only',['research/results/proof.json']);reg.append_state(temporary,id,'completed','synthetic only',['research/results/proof.json'])
 with pytest.raises(ValueError,match='independent'):reg.append_state(temporary,id,'accepted','synthetic only',['research/results/proof.json'])
 reg.append_state(temporary,id,'accepted','synthetic independently checked correctness',['research/results/proof.json'],True)
 assert reg.read(temporary)[id]['state']=='accepted';assert p.read_bytes()==original;assert len(reg.read(temporary)[id]['events'])==5

def test_ready_is_not_execution_claim():
 r=reg.read();p=r['EXP-TS-SEARCH-001']['protocol'];assert r['EXP-TS-SEARCH-001']['state']=='ready'and p['execution_ready']is False and p['full_experiment_command']is None
 assert 'not yet implemented'in p['next_action'].lower()or 'implement'in p['next_action'].lower()

def test_local_markdown_links_resolve():
 bad=[]
 for p in [ROOT/'MASTER_PLAN.md',*R.glob('*.md')]:
  for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
   if '://'not in link and not(p.parent/link.split('#')[0]).exists():bad.append((p.name,link))
 assert not bad

def test_planning_branch_does_not_include_pipeline_changes():
 base='0a08c3d7d6003947eb6205fdc58e981150bcd5ca';paths=subprocess.check_output(['git','-C',str(ROOT),'diff','--name-only',base],text=True).splitlines();paths+=subprocess.check_output(['git','-C',str(ROOT),'ls-files','--others','--exclude-standard'],text=True).splitlines();assert paths and all(p=='MASTER_PLAN.md'or p.startswith('research/')for p in paths)

def test_later_result_overwrite_is_detected(temporary):
 id='EXP-TS-SEARCH-001';h=temporary/'tools/synthetic_harness.py';h.write_text('# test metadata only\n');p=temporary/'results/proof.json';p.write_text('{"value":1}')
 reg.register_implementation(temporary,id,'python research/tools/synthetic_harness.py','research/tools/synthetic_harness.py',temporary.parent);reg.append_state(temporary,id,'running','synthetic',['research/results/proof.json']);p.write_text('{"value":2}')
 with pytest.raises(ValueError,match='evidence changed'):reg.read(temporary)
