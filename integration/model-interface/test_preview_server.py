"""The public draft may populate picks and past chips, never private finances."""
from datetime import datetime, timedelta, timezone
from importlib import util
from pathlib import Path

import pytest

spec = util.spec_from_file_location('serve_preview', Path(__file__).with_name('serve-preview.py'))
preview = util.module_from_spec(spec)
spec.loader.exec_module(preview)


def outgoing(active_chip=None):
    return {
        'entry/21/': {'id': 21, 'current_event': 11, 'last_deadline_bank': 20},
        'entry/21/event/11/picks/': {
            'active_chip': active_chip, 'entry_history': {'event': 11, 'bank': 20},
            'picks': [{'element': i + 200, 'position': i, 'purchase_price': 50} for i in range(15, 0, -1)],
        },
        'entry/21/history/': {'chips': [{'name': 'bboost', 'event': 9}]},
    }


def test_official_draft_has_ordered_picks_and_no_finances():
    result = preview.squad_draft(21, 12, outgoing().__getitem__)
    assert result['draft_only'] and result['source_gw'] == 11 and result['gw'] == 12
    assert result['chips_used']['bench_boost'] == [9]
    assert result['squad'] == [{'id': i} for i in range(201, 216)]
    assert not {'bank_tenths', 'free_transfers', 'observed_at'} & result.keys()


def test_free_hit_and_wrong_gameweek_are_rejected():
    with pytest.raises(ValueError, match='midlertidigt'):
        preview.squad_draft(21, 12, outgoing('freehit').__getitem__)
    with pytest.raises(ValueError, match='Ingen tidligere'):
        preview.squad_draft(21, 11, outgoing().__getitem__)


def test_worker_rejects_expired_future_and_closed_forecasts():
    cutoff = datetime(2026, 11, 23, 3, 30, tzinfo=timezone.utc)
    deadline = cutoff + timedelta(days=2)
    forecast = {'data_asof': cutoff.isoformat(), 'origin_deadline': deadline.isoformat()}
    assert preview.fresh_forecast(forecast, cutoff + timedelta(hours=36))
    assert not preview.fresh_forecast(forecast, cutoff + timedelta(hours=37))
    assert not preview.fresh_forecast(forecast, cutoff - timedelta(seconds=1))
    assert not preview.fresh_forecast(forecast, deadline)
