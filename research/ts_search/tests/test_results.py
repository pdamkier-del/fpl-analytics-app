from pathlib import Path
import json,sys,hashlib
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'research/ts_search/code'))
from verify_results import verify
RESULT=ROOT/'research/results/EXP-TS-SEARCH-001/initial-run/results.json'
def test_archived_paths_replay_under_independent_scalar_rules_and_costs():
 r=verify(RESULT);assert r['cases']==42 and r['exact_path_nominations_independently_replayed']==504
 assert r['D01_hand_witness_matches']and r['protocol_unchanged']and r['implementation_unchanged']

def test_preexecution_registration_precedes_state_and_results():
 events=[json.loads(x)for x in(ROOT/'research/events.jsonl').read_text().splitlines()];result=json.loads(RESULT.read_text());impl=next(e for e in events if e['sha256']==result['initial_registration_event_sha256']);running=next(e for e in events if e['experiment_id']=='EXP-TS-SEARCH-001'and e['kind']=='state_changed'and e['state']=='running')
 assert impl['kind']=='implementation_registered'and impl['sequence']<running['sequence'];assert impl['harness_sha256']==result['implementation_sha256']
 assert result['input_sha256']==hashlib.sha256((ROOT/'research/ts_search/inputs/instances.json').read_bytes()).hexdigest()

def test_restricted_optimum_is_labelled_and_raw_roundoff_not_hidden():
 result=json.loads(RESULT.read_text())
 for r in result['rows']:
  if r['level']=='restricted_DNP':assert r['pool']==15 and r['scenarios']==8 and 'no transfers' in r['nomination_domain']
 assert result['status']=='completed'and result['elapsed_seconds']<120 and not result['not_run']
