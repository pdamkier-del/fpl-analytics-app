import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('current_checkpoint', ROOT/'scripts/current_diagnostic_checkpoint.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def inputs(tmp_path, monkeypatch, **overrides):
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    monkeypatch.setattr(m, 'SELECTOR', tmp_path/'model/checkpoints/current-diagnostic.json')
    monkeypatch.setenv('GITHUB_RUN_ID', '123')
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '1')
    monkeypatch.setenv('GITHUB_REPOSITORY', 'pdamkier-del/fpl-analytics-app')
    cutoff='2026-10-10T20:02:27Z'
    files={
        'app/vfinal-diagnostic.json':dict(data_asof=cutoff,gws=list(range(7,13)),locked_model_active=False),
        'app/integration-validation.json':dict(validation_only=True,forecast_cutoff=cutoff,gw=7,locked_model_active=False,**overrides),
        'work/live-final-model/canonical_raw_rebuild.json':dict(passed=True,cutoff=cutoff),
        'work/live-final-model/source_manifest.json':dict(sources=[]),
    }
    for name,obj in files.items():
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj))

def test_old_manager_example_blocks_publication(tmp_path,monkeypatch):
    inputs(tmp_path,monkeypatch)
    p=tmp_path/'app/integration-validation.json'
    obj=json.loads(p.read_text());obj['forecast_cutoff']='2026-10-10T14:39:56Z';p.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='does not match'):m.package()
    assert not m.SELECTOR.exists()

def test_personal_or_unlabelled_example_cannot_be_published(tmp_path,monkeypatch):
    inputs(tmp_path,monkeypatch)
    p=tmp_path/'app/integration-validation.json'
    obj=json.loads(p.read_text());obj['validation_only']=False;p.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='does not match'):m.package()

def test_current_synthetic_example_allows_immutable_snapshot(tmp_path,monkeypatch):
    inputs(tmp_path,monkeypatch);m.package()
    result=json.loads(m.SELECTOR.read_text())
    assert result['cutoff']=='2026-10-10T20:02:27Z'
    assert result['locked_model_active'] is False
    assert (tmp_path/'model/checkpoints/releases/diagnostic-123-1/manifest.json').read_bytes()==m.SELECTOR.read_bytes()
