import copy
from datetime import datetime, timedelta, timezone
import pytest
from fpl_v1_1_model.forecast_snapshot import seal_forecast
from test_unified_b_chain import unified_fixture
from b_snapshot_policy import validate_snapshot, manager_snapshot_context


def fixture():
    f,s=unified_fixture();now=datetime.now(timezone.utc)
    f['data_asof']=(now-timedelta(hours=30)).isoformat()
    f['freshness_limit_hours']=6
    s['observed_at']=(now-timedelta(minutes=1)).isoformat()
    s['bank_tenths']=50
    return seal_forecast(f),s,now.isoformat()


def test_snapshot_runs_real_six_gw_without_rewriting_forecast_or_state():
    from service.preview_manager_job import calculate
    import service.manager_job as original
    f,s,now=fixture();before=copy.deepcopy((f,s));aliases=(original.run,original.parse_state)
    with pytest.raises(ValueError,match='freshness'):
        calculate(f,s)
    result=calculate(f,s,snapshot_at=now)
    assert (f,s)==before and (original.run,original.parse_state)==aliases
    assert result['forecast_cutoff']==result['model_asof']==f['data_asof']
    assert result['decision_at']==now and result['forecast_sha256']==f['forecast_sha256']
    assert len(result['plan']['path'])==6
    assert result['current_team']['expected_score']==pytest.approx(47.6)
    assert result['forecast_policy']=='latest_verified_snapshot_v1'


@pytest.mark.parametrize('case',['deadline','future_state','future_model','naive'])
def test_snapshot_rejects_invalid_time_boundaries(case):
    f,s,now=fixture();at=datetime.fromisoformat(now)
    if case=='deadline':f['origin_deadline']=(at-timedelta(seconds=1)).isoformat()
    if case=='future_state':s['observed_at']=(at+timedelta(hours=1)).isoformat()
    if case=='future_model':f['data_asof']=(at+timedelta(hours=1)).isoformat()
    if case=='naive':now='2026-10-22T07:00:00'
    f=seal_forecast(f)
    with pytest.raises(ValueError):validate_snapshot(f,s,now)


def test_snapshot_context_restores_production_aliases_on_exception():
    import service.manager_job as original
    f,s,now=fixture();aliases=(original.run,original.parse_state)
    with pytest.raises(RuntimeError):
        with manager_snapshot_context(f,s,now):raise RuntimeError('interrupted')
    assert (original.run,original.parse_state)==aliases


def test_snapshot_policy_is_opt_in_and_never_accepted_on_production_route():
    from service.app import app,ORIGIN
    with app.test_client()as client:
        response=client.post('/plans',headers={'Origin':ORIGIN},json={
            'state':{},'forecast_cutoff':'2026-10-22T07:00:00Z',
            'forecast_policy':'latest_verified_snapshot_v1'})
        assert response.status_code==400


def test_shared_ts_adapter_contains_no_other_changes_to_frozen_default():
    from pathlib import Path
    from check_snapshot_adapter import check
    text=(Path(__file__).resolve().parents[1]/'scripts/run_live_locked_ts.py').read_text()
    assert check(text)
    with pytest.raises(ValueError):check(text.replace("'plan_gain_over_hold':planned.objective-baseline_value", "'plan_gain_over_hold':planned.objective+baseline_value"))


def test_snapshot_browser_policy_and_production_window_are_separate():
    from pathlib import Path
    import subprocess
    subprocess.run(['node','tests/test_latest_snapshot.js'],cwd=Path(__file__).resolve().parents[1],check=True)


def test_api_snapshot_checks_real_deadline_but_tolerates_old_prices(monkeypatch):
    import io,json
    from service import app as api
    f,s,now=fixture()
    boot={'events':[{'id':7,'is_next':True,'deadline_time':f['origin_deadline']}],
          'elements':[dict(id=p['id'],now_cost=99,team=p['team_id'],element_type=p['position'])for p in f['players']]}
    monkeypatch.setattr(api,'urlopen',lambda *a,**k:io.BytesIO(json.dumps(boot).encode()))
    assert api.verify_snapshot_now(f)==7
    with pytest.raises(ValueError):api.verify_current_window(f,boot,preview=True)
    boot['events'][0]['id']=8
    with pytest.raises(ValueError):api.verify_snapshot_now(f)
