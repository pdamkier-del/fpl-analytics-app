"""Prevent a pure UI release from rolling back a newer live B forecast."""
import io,json
from pathlib import Path
import pytest
from publish_mm_preview import require_current_preview

@pytest.mark.parametrize('branch',['current','gk'])
def test_reject_newer_served_snapshot(tmp_path,branch):
    for part in ['current','gk']:
        folder=tmp_path/part;folder.mkdir()
        (folder/'forecast.json').write_text(json.dumps({'data_asof':'2026-10-19T20:00:00+00:00'}))
    def fetch(url,**kwargs):
        timestamp='2026-10-20T10:00:00Z' if '/'+branch+'/' in url else '2026-10-19T20:00:00Z'
        return io.BytesIO(json.dumps({'data_asof':timestamp}).encode())
    with pytest.raises(ValueError,match='Newer B forecast'):
        require_current_preview(tmp_path,fetch)

@pytest.mark.parametrize('served',['2026-10-19T20:00:00Z','2026-10-20T10:00:00Z'])
def test_same_or_newer_incoming_allowed(tmp_path,served):
    for part in ['current','gk']:
        folder=tmp_path/part;folder.mkdir()
        (folder/'forecast.json').write_text(json.dumps({'data_asof':'2026-10-20T10:00:00+00:00'}))
    require_current_preview(tmp_path,lambda *args,**kwargs:io.BytesIO(json.dumps({'data_asof':served}).encode()))
