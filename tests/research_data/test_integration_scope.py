import json
import os
from pathlib import Path
import subprocess
import pytest
import archive
from evaluation_ops import ts_capture as cap


def test_only_intended_workflow_and_integrations_change():
    root=archive.ROOT
    paths=subprocess.check_output(['git','-C',str(root),'diff','--name-only','876e61b0f847d6987d64000cd58af90ba94dd036'],text=True).splitlines()
    assert all(p=='.github/workflows/mm-current-preview-publication.yml' or p.startswith(('integration/','tests/','evaluation_ops/','analysis/followup-41-20261122/'))for p in paths)
    text=(root/'.github/workflows/mm-current-preview-publication.yml').read_text()
    job=text.split('  permanent-research-archive:\n',1)[1].split('  preview:\n',1)[0]
    assert 'needs: [current, verified]'in job and 'needs: [preview]'not in job
    assert '--clobber'not in (root/'integration/research-data/releases.py').read_text()
    assert 'upload-artifact'not in job and 'pages:'not in job
    assert 'research_archive_only:'in text and '!inputs.research_archive_only'in text


def test_runtime_hash_mismatch_rejects_capture(monkeypatch,tmp_path):
    root=tmp_path/'runtime';path=root/'integration/research-data';path.mkdir(parents=True)
    (root/'source.py').write_text('altered')
    (path/'runtime-receipt.json').write_text(json.dumps(dict(model_source=archive.PIN,files={'source.py':'0'*64})))
    monkeypatch.setattr(cap,'ROOT',root)
    with pytest.raises(cap.Rejected)as error:cap.runtime_identity()
    assert error.value.code=='runtime_identity_changed'


def test_installer_repeat_and_models_unchanged():
    value=os.environ.get('FPL_CAPTURE_RUNTIME')
    if not value:pytest.skip('Set FPL_CAPTURE_RUNTIME to installed disposable runtime')
    runtime=Path(value)
    command=[os.sys.executable,str(archive.ROOT/'integration/research-data/install_private_hook.py'),value]
    before=(runtime/'service/app.py').read_bytes()
    subprocess.run(command,check=True,capture_output=True)
    assert (runtime/'service/app.py').read_bytes()==before
    expected=json.loads((archive.ROOT/'integration/research-data/frozen-source-hashes.json').read_text())
    for name,h in expected.items():
        if name!='service/app.py':assert archive.sha((runtime/name).read_bytes())==h
