import base64
import json
from types import SimpleNamespace
import pytest
import archive
import computation_receipt as receipt


@pytest.mark.parametrize('direct',[False,True])
def test_original_producer_source_and_clock(monkeypatch,direct):
    repo='pdamkier-del/fpl-analytics-app'
    name='current'if direct else'current / current'
    run=dict(head_repository={'full_name':repo},head_sha=archive.PIN,
             path='.github/workflows/mm-current-live-preview.yml'if direct else'.github/workflows/mm-current-preview-publication.yml',
             conclusion='success')
    workflow=(archive.ROOT/'.github/workflows/mm-current-preview-publication.yml').read_bytes()
    def api(args,**kw):
        path=args[-1]
        if '/jobs?'in path:doc={'jobs':[dict(id=1,name=name,status='completed',conclusion='success',started_at='2026-11-22T10:00:00Z',completed_at='2026-11-22T10:01:00Z')]}
        elif '/contents/'in path:doc={'content':base64.b64encode(workflow).decode()}
        else:doc=run
        return SimpleNamespace(returncode=0,stdout=json.dumps(doc).encode())
    monkeypatch.setattr(receipt.subprocess,'run',api)
    proof=receipt.collect(repo,'123')
    assert proof['producer_job_name']==name and proof['numerical_source']==archive.PIN
    assert 'upper bound'in proof['clock_basis']


def test_foreign_run_rejected_before_any_download(monkeypatch):
    doc={'head_repository':{'full_name':'different/repo'}}
    monkeypatch.setattr(receipt.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=json.dumps(doc).encode()))
    with pytest.raises(ValueError,match='Foreign'):receipt.collect('pdamkier-del/fpl-analytics-app','123')
