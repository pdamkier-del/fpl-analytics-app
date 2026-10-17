"""Candidate route privacy and unchanged original Python planning."""
import json
from datetime import datetime,timedelta
import pytest
from service import app as api
from test_mm_locked_bridge import ts_fixture
from fpl_v1_1_model.forecast_snapshot import seal_forecast


def official(f):return dict(events=[dict(id=f['gws'][0],is_next=True,deadline_time=f['origin_deadline'])],elements=[dict(id=p['id'],team=p['team_id'],element_type=p['position'],now_cost=p['price_tenths']) for p in f['players']])

def candidate():
    f,s=ts_fixture();f.update(mm_version='individual-B-formation-pmf-preview.1',minute_sampler_audit={'sampler':'locked'})
    return seal_forecast(f),s

def test_strict_separation_of_models_scope_and_minute_sampler():
    f,_=candidate();assert api.verify_current_window(f,official(f),preview=True)==7
    with pytest.raises(ValueError):api.verify_current_window(f,official(f))
    for mutation in [dict(scope='historical_replay'),dict(minute_sampler_audit={'sampler':'candidate_B'}),dict(model='original_locked_vFinal_diagnostic')]:
        with pytest.raises(ValueError):api.verify_current_window({**f,**mutation},official(f),preview=True)
    with pytest.raises(ValueError):api.verify_current_window(f,official(f),datetime.fromisoformat(f['origin_deadline'])+timedelta(seconds=1),preview=True)

def test_real_private_candidate_TS_job_and_capability_without_public_state(monkeypatch,tmp_path):
    from service.manager_job import calculate
    f,s=candidate();paths=[]
    class Immediate:
        def __init__(self,target,**kwargs):self.target=target
        def start(self):self.target()
    def public(path):
        paths.append(path)
        if path=='mm-preview/current/forecast.json':return json.dumps(f).encode()
        if path=='current-players.json':return b'{"next_gw":7}'
        raise AssertionError(path)
    def compute(*args,**kwargs):
        body=json.loads((tmp_path/'input.json').read_text());result=calculate(body['forecast'],body['state'])
        (tmp_path/'result.json').write_text(json.dumps(result,allow_nan=False))
        return type('Done',(),{'returncode':0})()
    monkeypatch.setattr(api.threading,'Thread',Immediate);monkeypatch.setattr(api.tempfile,'mkdtemp',lambda **kw:str(tmp_path))
    monkeypatch.setattr(api,'get_public',public);monkeypatch.setattr(api,'verify_official_now',lambda f,**kw:api.verify_current_window(f,official(f),**kw));monkeypatch.setattr(api.subprocess,'run',compute)
    with api.app.test_client() as c:
        r=c.post('/preview/plans',json=dict(state=s,forecast_cutoff=f['data_asof'],forecast_sha256=f['forecast_sha256']),headers={'Origin':api.ORIGIN});receipt=r.get_json()
        try:
            assert r.status_code==202
            assert c.get('/plans/'+receipt['id']).status_code==404
            r=c.get('/plans/'+receipt['id'],headers={'X-Plan-Key':receipt['key']});assert r.status_code==200
            plan=r.get_json()['plan'];assert plan['calculation_runtime']=='original_locked_python'
            assert len(plan['plan']['path'])==6 and len(plan['lineup'])==15
            assert plan['forecast_sha256']==f['forecast_sha256'] and not plan['locked_model_active']
            assert not (tmp_path/'input.json').exists()
            assert paths==['mm-preview/current/forecast.json','current-players.json','mm-preview/current/forecast.json']
        finally:api.jobs.pop(receipt['id'],None)

def test_candidate_source_failure_never_falls_back_to_original(monkeypatch,tmp_path):
    paths=[]
    class Immediate:
        def __init__(self,target,**kwargs):self.target=target
        def start(self):self.target()
    def absent(path):paths.append(path);raise OSError('source unavailable')
    monkeypatch.setattr(api.threading,'Thread',Immediate);monkeypatch.setattr(api.tempfile,'mkdtemp',lambda **kw:str(tmp_path));monkeypatch.setattr(api,'get_public',absent)
    with api.app.test_client() as c:
        r=c.post('/preview/plans',json=dict(state={},forecast_cutoff='synthetic',forecast_sha256='a'*64),headers={'Origin':api.ORIGIN});receipt=r.get_json()
        try:
            assert c.get('/plans/'+receipt['id'],headers={'X-Plan-Key':receipt['key']}).status_code==422
            assert paths==['mm-preview/current/forecast.json']
        finally:api.jobs.pop(receipt['id'],None)


def test_original_clients_without_content_id_remain_compatible_but_preview_requires_one(monkeypatch,tmp_path):
    class Deferred:
        def __init__(self,target,**kwargs):pass
        def start(self):pass
    monkeypatch.setattr(api.threading,'Thread',Deferred)
    monkeypatch.setattr(api.tempfile,'mkdtemp',lambda **kw:str(tmp_path))
    body=dict(state={},forecast_cutoff='synthetic')
    with api.app.test_client() as c:
        assert c.post('/preview/plans',json=body,headers={'Origin':api.ORIGIN}).status_code==400
        result=c.post('/plans',json=body,headers={'Origin':api.ORIGIN})
        assert result.status_code==202
        api.jobs.pop(result.get_json()['id'],None)
