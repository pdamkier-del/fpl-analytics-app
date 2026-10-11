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
    classic=tmp_path/'my-team-classic.html';classic.write_text('<script src="weekly-app.js"></script>')
    version_frontend_assets(tmp_path)
    first=page.read_text()
    assert hashlib.sha256(b'first').hexdigest()[:16] in first
    assert hashlib.sha256(b'first').hexdigest()[:16] in classic.read_text()
    version_frontend_assets(tmp_path)
    assert page.read_text()==first
    asset.write_text('second');version_frontend_assets(tmp_path)
    assert hashlib.sha256(b'second').hexdigest()[:16] in page.read_text()
    assert editor.read_text()=='<a href="overview.html">team</a>'

def test_classic_html_navigation_version_tracks_inline_fixes(tmp_path):
    (tmp_path/'classic-nav.js').write_text('navigation')
    page=tmp_path/'my-team-classic.html'
    page.write_text('<html><head></head><body><script>first inline</script><script src="classic-nav.js"></script></body></html>')
    version_frontend_assets(tmp_path)
    first=page.read_text()
    assert 'name="fpl-ui-version"' in first
    version_frontend_assets(tmp_path)
    assert page.read_text()==first
    page.write_text(page.read_text().replace('first inline','fixed inline'))
    version_frontend_assets(tmp_path)
    assert page.read_text().split('fpl-ui-version')[1]!=first.split('fpl-ui-version')[1]
