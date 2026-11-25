from pathlib import Path
import hashlib
import importlib.util
import json
import math
import sys
import pytest
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'research/mm_pm_live'),str(ROOT/'research/mm_pm_live/tests'),str(ROOT/'research/mm_pm_maintenance'),str(ROOT/'research/tools')]
import metrics,evaluate,registry
from fixtures import fixture
from labels import normalize
from evaluate_roundoff import canonical_probability,guarded_probabilities,score


def test_roundoff_only_and_exact_restoration():
    original=metrics.probability
    with guarded_probabilities()as audit:
        assert metrics.probability(-2.5e-15)==0
        assert metrics.probability(1+2e-15)==1
        for x in [0.,.2,.5,1.]:assert metrics.probability(x)==original(x)
        assert audit['normalized_calls']==2
    assert metrics.probability is original
    for bad in [-1e-5,1.00001,float('nan'),float('inf'),True]:
        with pytest.raises(ValueError):canonical_probability(bad)
    with pytest.raises(RuntimeError):
        with guarded_probabilities():raise RuntimeError('fixture only')
    assert metrics.probability is original


def test_original_valid_fixture_metrics_identical_and_raw_untouched():
    f,mm,b,fx,p,ids,h=fixture();n=normalize(f,b,fx,p,ids,h)
    before=json.dumps([f,mm],sort_keys=True)
    original=evaluate.score(f,mm,b,fx,n);corrected=score(f,mm,b,fx,n)
    assert corrected.pop('numeric_implementation_audit')['normalized_calls']==0
    assert corrected==original and json.dumps([f,mm],sort_keys=True)==before
    mm['players'][0]['p_play']=-2e-15
    before=json.dumps([f,mm],sort_keys=True)
    with pytest.raises(ValueError,match='Probability'):evaluate.score(f,mm,b,fx,n)
    result=score(f,mm,b,fx,n)
    assert result['numeric_implementation_audit']['normalized_calls']>0
    assert json.dumps([f,mm],sort_keys=True)==before


def test_current_registry_metadata_replaces_snapshot_count_only():
    records=registry.read();registered=[json.loads(line)for line in(registry.R/'events.jsonl').read_text().splitlines()if json.loads(line)['kind']=='registered']
    assert set(records)=={e['experiment_id']for e in registered}
    assert registry.validate()['experiments']==len(registered)
    prior=json.loads((ROOT/'research/evidence/mm-pm-cycle-20261125/prior-registry.json').read_text())
    for p,h in prior['protocols'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
    protected=records['EXP-MM-SUB-20261108']['protocol'];assert protected['sample_size']['minimum_gws']==8 and protected['sample_size']['minimum_matches']==80


def test_reconciliation_preserves_state_and_implementation_at_event_time():
    states={};implementations={};count=0
    for line in(registry.R/'events.jsonl').read_text().splitlines():
        e=json.loads(line);i=e['experiment_id']
        if e['kind']=='registered':states[i]=e['state'];implementations[i]=None
        elif e['kind']=='state_changed':states[i]=e['state']
        elif e['kind']=='implementation_registered':implementations[i]=e['harness_sha256']
        elif e['kind']=='evidence_reconciled':
            count+=1;before=(states[i],implementations[i]);assert e['state']==states[i]and not e.get('harness');assert before==(states[i],implementations[i])
    assert count>=11
    records=registry.read()
    assert states=={i:r['state']for i,r in records.items()}
    assert implementations=={i:r['implementation']['harness_sha256']if r['implementation']else None for i,r in records.items()}


def test_pinned_v2_remains_reproducible():
    manifest=json.loads((ROOT/'research/mm_pm_live/implementation-manifest.v2.json').read_text())
    for p,h in manifest['files'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
