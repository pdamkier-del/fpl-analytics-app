"""Explicit live B snapshot decisions. Never change model or manager timestamps."""
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial

POLICY = 'latest_verified_snapshot_v1'


def timestamp(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Snapshot decision timestamps must include a timezone')
    return parsed


def validate_snapshot(forecast, state, decision_at):
    from b_chain_contract import VERSION, validate_forecast
    if forecast.get('model') != VERSION:
        raise ValueError('Snapshot mode is limited to the unified B preview')
    validate_forecast(forecast)
    now = timestamp(decision_at)
    if now > datetime.now(timezone.utc):
        raise ValueError('Future snapshot decision')
    if timestamp(forecast['data_asof']) > now or timestamp(state['observed_at']) > now:
        raise ValueError('Future model or manager observation')
    if now >= timestamp(forecast['origin_deadline']):
        raise ValueError('Snapshot deadline passed; a new gameweek forecast is required')


@contextmanager
def manager_snapshot_context(forecast, state, decision_at):
    """Only used inside the isolated B subprocess; restore aliases on failure."""
    validate_snapshot(forecast, state, decision_at)
    import service.manager_job as original
    run, parse = original.run, original.parse_state
    original.run = partial(run, snapshot_at=decision_at)
    original.parse_state = lambda raw, meta, gw, cutoff: parse(raw, meta, gw, decision_at)
    try:
        yield
    finally:
        original.run, original.parse_state = run, parse
