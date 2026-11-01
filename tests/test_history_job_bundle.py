"""Pinned public replay inputs cannot be substituted or write outside the job."""
import json,hashlib
import pytest
import service.history_job as worker

class Reply:
    def __init__(self,raw):self.content=raw
    def raise_for_status(self):pass

def test_shared_bundle_rejects_changed_manifest_before_any_output(monkeypatch,tmp_path):
    config=tmp_path/'config.json';config.write_text(json.dumps({'commit':'a'*40,'path':'analysis/results/history-refresh-public-20261029','manifest_sha256':'0'*64}));monkeypatch.setattr(worker,'CONFIG',config);monkeypatch.setattr(worker.requests,'get',lambda *a,**k:Reply(b'{"changed":true}'))
    with pytest.raises(ValueError,match='checksum'):worker.download_bundle(tmp_path,'2026-27')
    assert not(tmp_path/'public-inputs').exists()

def test_shared_bundle_rejects_unexpected_paths_even_with_matching_manifest(monkeypatch,tmp_path):
    manifest={'schema':'fpl-shared-history-refresh-inputs-v1','season':'2026-27','model_source':worker.MODEL,'gws':[6],'files':{'../../escape':'a'*64}};raw=json.dumps(manifest).encode();config=tmp_path/'config.json';config.write_text(json.dumps({'commit':'a'*40,'path':'analysis/results/history-refresh-public-20261029','manifest_sha256':hashlib.sha256(raw).hexdigest()}));monkeypatch.setattr(worker,'CONFIG',config);monkeypatch.setattr(worker.requests,'get',lambda *a,**k:Reply(raw))
    with pytest.raises(ValueError,match='Incomplete'):worker.download_bundle(tmp_path,'2026-27')
    assert not(tmp_path/'public-inputs').exists()
