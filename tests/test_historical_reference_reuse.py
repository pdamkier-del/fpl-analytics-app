import hashlib
import json
from pathlib import Path
import pytest
from historical_reference_reuse import require_compatible

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'analysis/results/normal-match-correctness-20261025/historical-reference-reuse.json'


def test_other_reference_source_fails_before_any_cache_is_used():
    with pytest.raises(ValueError,match='not approved'):
        require_compatible(ROOT,'unknown','HEAD')


def test_changed_historical_dependency_fails_closed():
    m=json.loads(MANIFEST.read_text());name=next(iter(m['reviewed_file_sha256']))
    m['reviewed_file_sha256'][name]='0'*64
    with pytest.raises(ValueError,match='dependency changed'):
        require_compatible(ROOT,m['reference_source'],'HEAD',manifest=m)


def test_unreviewed_existing_changes_cannot_reuse_history(monkeypatch):
    import historical_reference_reuse as reuse
    m=json.loads(MANIFEST.read_text())
    # Isolate the diff guard from the deliberately changed B composition.
    # The separate dependency test above still checks fail-closed hashes.
    for group in ['reviewed_file_sha256','reviewed_additions_sha256']:
        m[group]={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()for name in m[group]}
    monkeypatch.setattr(reuse.subprocess,'check_output',lambda *a,**kw:'M\tsrc/fpl_v1_1_model/bps.py\n')
    with pytest.raises(ValueError,match='Unreviewed historical reference change'):
        require_compatible(ROOT,m['reference_source'],'HEAD',manifest=m)


def test_new_unreviewed_import_or_data_cannot_shadow_a_reference(monkeypatch):
    import historical_reference_reuse as reuse
    m=json.loads(MANIFEST.read_text())
    # Isolate the diff guard from the deliberately changed B composition.
    # The separate dependency test above still checks fail-closed hashes.
    for group in ['reviewed_file_sha256','reviewed_additions_sha256']:
        m[group]={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()for name in m[group]}
    monkeypatch.setattr(reuse.subprocess,'check_output',lambda *a,**kw:'A\tsrc/numpy/__init__.py\n')
    with pytest.raises(ValueError,match='Unreviewed historical reference addition'):
        require_compatible(ROOT,m['reference_source'],'HEAD',manifest=m)
