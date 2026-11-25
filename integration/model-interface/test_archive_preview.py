from datetime import datetime, timezone
import gzip
import hashlib
from importlib import util
import json
from pathlib import Path

import pytest

spec = util.spec_from_file_location('build_archive_preview', Path(__file__).with_name('build-archive-preview.py'))
preview = util.module_from_spec(spec)
spec.loader.exec_module(preview)


def test_live_window_checks_official_round_deadline_and_cutoff():
    manifest = {'origin_gw': 12, 'data_cutoff': '2026-11-23T03:30:00+00:00',
                'official_deadline': '2026-11-27T18:30:00+00:00'}
    news = {'next_gw': 12, 'deadline': '2026-11-27T18:30:00Z'}
    now = datetime(2026, 11, 23, 10, tzinfo=timezone.utc)
    assert preview.live_window(manifest, news, now)
    assert not preview.live_window(manifest, news, now.replace(day=25))
    assert not preview.live_window(manifest, {**news, 'next_gw': 13}, now)
    assert not preview.live_window(manifest, {**news, 'deadline': '2026-11-27T19:30:00Z'}, now)


def test_bundle_must_match_archive_and_probability_forecast(tmp_path):
    capture = tmp_path / 'capture'
    current, gk = capture / 'current', capture / 'gk'
    archive = tmp_path / 'archive'
    for folder in (current, gk, archive):
        folder.mkdir(parents=True)
    forecast = b'{"forecast_sha256":"original"}'
    bundle = b'{"forecast_sha256":"original","documents":{}}'
    (current / 'index.json').write_text(json.dumps({
        'forecast_sha256': 'original', 'existing_app_data_sha256': hashlib.sha256(bundle).hexdigest(),
    }))
    (current / 'existing-app-data.json').write_bytes(bundle)
    (current / 'forecast.json').write_bytes(forecast)
    (current / 'mm.json').write_bytes(b'{}')
    for filename in ('index.json', 'forecast.json', 'mm.json'):
        (archive / (filename + '.gz')).write_bytes(gzip.compress((current / filename).read_bytes()))
    (gk / 'forecast.json').write_bytes(forecast)
    (gk / 'gk-mm.json').write_bytes(b'{}')
    (gk / 'evidence.json').write_bytes(b'{}')
    (gk / 'index.json').write_text(json.dumps({
        'forecast_sha256': preview.sha(gk / 'forecast.json'),
        'mm_sha256': preview.sha(gk / 'gk-mm.json'),
        'evidence_sha256': preview.sha(gk / 'evidence.json'),
    }))
    manifest = {'forecast_sha256': 'original'}
    preview.verify_capture(capture, archive, manifest)

    (current / 'existing-app-data.json').write_bytes(b'{}')
    with pytest.raises(ValueError, match='App bundle checksum'):
        preview.verify_capture(capture, archive, manifest)
    (current / 'existing-app-data.json').write_bytes(bundle)

    (current / 'forecast.json').write_bytes(b'{}')
    with pytest.raises(ValueError, match='differs from the verified archive'):
        preview.verify_capture(capture, archive, manifest)
