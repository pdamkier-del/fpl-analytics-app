"""A new published UI must replace cached assets without changing navigation."""
import hashlib
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from publish_weekly_assets import version_frontend_assets

def test_published_asset_version_tracks_bytes_and_is_idempotent(tmp_path):
    asset=tmp_path/'weekly-app.js';asset.write_text('first')
    page=tmp_path/'overview.html';page.write_text('<script src="weekly-app.js?v=old"></script>')
    editor=tmp_path/'manager-state.html';editor.write_text('<a href="overview.html">team</a>')
    version_frontend_assets(tmp_path)
    first=page.read_text()
    assert hashlib.sha256(b'first').hexdigest()[:16] in first
    version_frontend_assets(tmp_path)
    assert page.read_text()==first
    asset.write_text('second');version_frontend_assets(tmp_path)
    assert hashlib.sha256(b'second').hexdigest()[:16] in page.read_text()
    assert editor.read_text()=='<a href="overview.html">team</a>'
