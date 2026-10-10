"""GW6 roster recovery must match the original immutable raw FPL source."""
import hashlib,importlib.util,json
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_recovered_roster_is_exact_original_predeadline_source(tmp_path):
    spec=importlib.util.spec_from_file_location('gw6_original_restore',ROOT/'scripts/restore_live_input_checkpoint.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.restore(tmp_path)
    archive=json.loads((ROOT/'work/live-final-model/predeadline_2026_archives/gw6.json').read_text())
    e=archive['evidence'];raw=(tmp_path/e['source_path']).read_bytes();source=json.loads(raw)
    assert hashlib.sha256(raw).hexdigest()==e['source_sha256']
    assert datetime.fromisoformat(e['snapshot_at_utc'])<datetime.fromisoformat(e['official_deadline'].replace('Z','+00:00'))
    assert next(g for g in source['events'] if g['id']==6)['is_next']
    expected=[dict(id=p['id'],team=p['team'],position=p['element_type'],name=p['web_name'],status=p['status'],news=p.get('news'),news_added=p.get('news_added'),chance_next=p.get('chance_of_playing_next_round')) for p in source['elements']]
    assert archive['players']==expected
    assert e['players']==len(expected)==667
    assert e['not_exact_deadline_completeness'] is True
