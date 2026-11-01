from datetime import datetime, timedelta, timezone
import pytest
from request_b_refresh import maybe_request

NOW = datetime(2026, 10, 21, 18, tzinfo=timezone.utc)


@pytest.mark.parametrize('status', ['queued', 'in_progress', 'waiting', 'pending', 'requested'])
def test_news_change_never_starts_duplicate_refresh(status):
    calls = []
    result = maybe_request('official_player_information_changed',
        [dict(status=status, created_at=(NOW-timedelta(hours=2)).isoformat())], lambda: calls.append(1), NOW)
    assert result['reason'] == 'refresh_already_in_flight' and not calls


def test_failed_refresh_has_bounded_retry_then_can_recover():
    calls = []
    run = dict(status='completed', created_at=(NOW-timedelta(minutes=29)).isoformat())
    assert not maybe_request('new_gameweek', [run], lambda: calls.append(1), NOW)['requested']
    result = maybe_request('new_gameweek', [run], lambda: calls.append(1), NOW+timedelta(minutes=2))
    assert result['requested'] and result['ref'] == 'main' and calls == [1]


def test_unchanged_news_never_dispatches():
    calls = []
    assert not maybe_request(None, [], lambda: calls.append(1), NOW)['requested']
    assert not calls


def test_verified_news_detects_changes_and_old_models_without_dispatch(tmp_path):
    import hashlib,json
    from collect_dashboard_news import build
    from request_b_refresh import refresh_reason
    base=tmp_path/'mm-preview';(base/'current').mkdir(parents=True);(base/'news').mkdir()
    player=dict(id=1,web_name='Example',team=1,element_type=3,now_cost=55,status='a',
        news='',news_added=None,chance_of_playing_next_round=100,chance_of_playing_this_round=100)
    raw=dict(events=[dict(is_next=True,id=8,deadline_time=(NOW+timedelta(days=2)).isoformat())],
        teams=[dict(id=1,name='Example club')],elements=[player])
    fresh=build(raw,NOW.isoformat())
    (base/'news/availability.json').write_text(json.dumps(fresh))
    forecast=dict(forecast_sha256='identity',gws=[8],data_asof=(NOW-timedelta(hours=2)).isoformat())
    data=dict(forecast_sha256='identity',documents={'current-players.json':{'players':[dict(
        fresh['players'][0],price=5.5)]}})
    index=dict(model='B-MM-PM-TS-v1',forecast_sha256='identity')
    def save(name,value,key):
        encoded=json.dumps(value).encode();(base/'current'/name).write_bytes(encoded)
        index[key]=hashlib.sha256(encoded).hexdigest()
        (base/'current/index.json').write_text(json.dumps(index))
    save('forecast.json',forecast,'forecast_file_sha256')
    save('existing-app-data.json',data,'existing_app_data_sha256')
    assert refresh_reason(tmp_path,NOW) is None
    player.update(status='i',news='Injury',chance_of_playing_next_round=0)
    (base/'news/availability.json').write_text(json.dumps(build(raw,NOW.isoformat())))
    assert refresh_reason(tmp_path,NOW)=='official_player_information_changed'
    (base/'news/availability.json').write_text(json.dumps(fresh))
    forecast['data_asof']=(NOW-timedelta(hours=7)).isoformat()
    save('forecast.json',forecast,'forecast_file_sha256')
    assert refresh_reason(tmp_path,NOW)=='model_source_older_than_six_hours'
    (base/'current/existing-app-data.json').write_text('{}')
    with pytest.raises(ValueError,match='Unverified preview file'):
        refresh_reason(tmp_path,NOW)
