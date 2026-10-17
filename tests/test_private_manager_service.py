"""Privacy boundaries on the real HTTP adapter, without publishing a manager."""
from pathlib import Path
import sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from service.app import app,jobs,ORIGIN

def test_origin_and_missing_state_rejected():
    with app.test_client() as c:
        assert c.post('/plans',json={}).status_code==403
        assert c.post('/plans',json={},headers={'Origin':ORIGIN}).status_code==400
        response=c.options('/plans',headers={'Origin':ORIGIN})
        assert response.headers['Access-Control-Allow-Origin']==ORIGIN
        assert c.options('/plans',headers={'Origin':'https://other.example'}).headers.get('Access-Control-Allow-Origin') is None

def test_private_job_requires_capability_and_expires(tmp_path):
    jobs['private-example']={'key':'secret-key','created':time.time(),'status':'completed','directory':tmp_path}
    (tmp_path/'result.json').write_text('{"private":true}')
    with app.test_client() as c:
        assert c.get('/plans/private-example').status_code==404
        assert c.get('/plans/private-example',headers={'X-Plan-Key':'wrong'}).status_code==404
        response=c.get('/plans/private-example',headers={'X-Plan-Key':'secret-key'})
        assert response.get_json()['plan']=={'private':True}
        assert response.headers['Cache-Control']=='no-store'
        jobs['private-example']['created']-=3601
        assert c.get('/plans/private-example',headers={'X-Plan-Key':'secret-key'}).status_code==410
    del jobs['private-example']

def test_busy_job_refuses_second_compute(tmp_path):
    jobs['running-example']={'key':'key','created':time.time(),'status':'running','directory':tmp_path}
    with app.test_client() as c:
        response=c.post('/plans',json={'state':{},'forecast_cutoff':'test','forecast_sha256':'a'*64},headers={'Origin':ORIGIN})
        assert response.status_code==429
    del jobs['running-example']

def test_corrupt_private_result_fails_closed(tmp_path):
    key='bad-result'
    jobs[key]={'key':'k','created':time.time(),'status':'completed','directory':tmp_path}
    try:
        with app.test_client() as c:
            missing=c.get('/plans/'+key,headers={'X-Plan-Key':'k'})
            assert missing.status_code==422
            assert missing.get_json()['status']=='failed'
            (tmp_path/'result.json').write_text('{not json')
            corrupt=c.get('/plans/'+key,headers={'X-Plan-Key':'k'})
            assert corrupt.status_code==422
            (tmp_path/'result.json').write_text('[]')
            wrong_shape=c.get('/plans/'+key,headers={'X-Plan-Key':'k'})
            assert wrong_shape.status_code==422
    finally:
        del jobs[key]

def test_service_health_never_claims_ready_when_original_runtime_unavailable(monkeypatch):
    import service.app as api
    monkeypatch.setattr(api,'original_runtime_ready',lambda:False)
    with app.test_client() as c:
        r=c.get('/health')
        assert r.status_code==503
        assert r.get_json()['status']=='unavailable'
        assert r.get_json()['locked_model_active'] is False

def test_service_health_reports_original_runtime_when_available(monkeypatch):
    import service.app as api
    monkeypatch.setattr(api,'original_runtime_ready',lambda:True)
    with app.test_client() as c:
        r=c.get('/health')
        assert r.status_code==200
        assert r.get_json()['runtime']=='original_locked_python'

def test_private_compute_rejects_unavailable_original_runtime(monkeypatch):
    import service.app as api
    monkeypatch.setattr(api,'original_runtime_ready',lambda:False)
    with app.test_client() as c:
        r=c.post('/plans',json={'state':{},'forecast_cutoff':'2026-10-11T08:00:00Z'},headers={'Origin':ORIGIN})
        assert r.status_code==503
        assert 'ikke klar' in r.get_json()['error']

def test_service_checks_fresh_official_window_without_changing_model():
    from datetime import datetime,timezone
    import pytest
    from service.app import verify_current_window
    f=dict(model='original_locked_vFinal_diagnostic',locked_model_active=False,gws=list(range(7,13)),origin_deadline='2026-10-17T10:00:00Z',data_asof='2026-10-11T09:00:00Z',freshness_limit_hours=24)
    f['players']=[dict(id=1,price_tenths=50,team_id=1,position=4)]
    b={'events':[dict(id=7,is_next=True,deadline_time=f['origin_deadline'])],'elements':[dict(id=1,now_cost=50,team=1,element_type=4)]}
    assert verify_current_window(f,b,datetime(2026,10,11,10,tzinfo=timezone.utc))==7
    with pytest.raises(ValueError,match='freshness'):verify_current_window(f,b,datetime(2026,10,12,10,tzinfo=timezone.utc))
    b['events'][0]['id']=8
    with pytest.raises(ValueError,match='changed'):verify_current_window(f,b,datetime(2026,10,11,10,tzinfo=timezone.utc))

def test_worker_timeout_removes_private_input_and_returns_safe_failure(monkeypatch,tmp_path):
    import json,subprocess
    import service.app as api
    class ImmediateThread:
        def __init__(self,target,**kwargs):self.target=target
        def start(self):self.target()
    monkeypatch.setattr(api.threading,'Thread',ImmediateThread)
    monkeypatch.setattr(api,'original_runtime_ready',lambda:True)
    monkeypatch.setattr(api.tempfile,'mkdtemp',lambda **kwargs:str(tmp_path))
    monkeypatch.setattr(api,'get_public',lambda name:json.dumps({'data_asof':'cutoff','gws':[7]} if name=='vfinal-diagnostic.json' else {'next_gw':7}).encode())
    monkeypatch.setattr(api,'verify_official_now',lambda forecast:7)
    monkeypatch.setattr(api,'require_forecast_snapshot',lambda forecast,expected:expected)
    def timeout(*args,**kwargs):raise subprocess.TimeoutExpired('private worker',1800)
    monkeypatch.setattr(api.subprocess,'run',timeout)
    with app.test_client() as c:
        response=c.post('/plans',json={'state':{'private':'test-only'},'forecast_cutoff':'cutoff','forecast_sha256':'a'*64},headers={'Origin':ORIGIN})
        receipt=response.get_json();identifier=receipt['id']
        try:
            assert response.status_code==202
            assert not (tmp_path/'input.json').exists()
            result=c.get('/plans/'+identifier,headers={'X-Plan-Key':receipt['key']})
            assert result.status_code==422
            assert 'timeout' in result.get_json()['error']
            assert 'test-only' not in result.get_data(as_text=True)
        finally:del jobs[identifier]

def test_lost_submission_receipt_resumes_same_private_job(monkeypatch,tmp_path):
    import service.app as api
    starts=[]
    class DeferredThread:
        def __init__(self,target,**kwargs):self.target=target
        def start(self):starts.append(self.target)
    monkeypatch.setattr(api.threading,'Thread',DeferredThread)
    monkeypatch.setattr(api,'original_runtime_ready',lambda:True)
    monkeypatch.setattr(api.tempfile,'mkdtemp',lambda **kwargs:str(tmp_path))
    body={'state':{'synthetic':'privacy test only'},'forecast_cutoff':'cutoff','forecast_sha256':'a'*64,'request_id':'a'*32,'request_key':'b'*43}
    with app.test_client() as c:
        try:
            first=c.post('/plans',json=body,headers={'Origin':ORIGIN})
            retry=c.post('/plans',json=body,headers={'Origin':ORIGIN})
            assert first.status_code==retry.status_code==202
            assert first.get_json()==retry.get_json()
            assert len(starts)==1
            changed=c.post('/plans',json={**body,'state':{'synthetic':'different'}},headers={'Origin':ORIGIN})
            assert changed.status_code==409
            wrong_key=c.post('/plans',json={**body,'request_key':'c'*43},headers={'Origin':ORIGIN})
            assert wrong_key.status_code==409
        finally:jobs.pop(body['request_id'],None)

def test_malformed_private_submission_capability_is_rejected(monkeypatch):
    import service.app as api
    monkeypatch.setattr(api,'original_runtime_ready',lambda:True)
    with app.test_client() as c:
        response=c.post('/plans',json={'state':{},'forecast_cutoff':'test','forecast_sha256':'a'*64,'request_id':'too-short','request_key':'guess'},headers={'Origin':ORIGIN})
        assert response.status_code==400

def test_worker_rejects_same_cutoff_content_change(monkeypatch,tmp_path):
    import json
    import service.app as api
    from fpl_v1_1_model.forecast_snapshot import seal_forecast
    forecast=seal_forecast({'data_asof':'cutoff','gws':[7],'players':[{'xp':5}]})
    updated=seal_forecast({**forecast,'players':[{'xp':6}]})
    feeds=iter([forecast,updated]);calls=[]
    class ImmediateThread:
        def __init__(self,target,**kwargs):self.target=target
        def start(self):self.target()
    monkeypatch.setattr(api.threading,'Thread',ImmediateThread)
    monkeypatch.setattr(api,'original_runtime_ready',lambda:True)
    monkeypatch.setattr(api.tempfile,'mkdtemp',lambda **kwargs:str(tmp_path))
    monkeypatch.setattr(api,'get_public',lambda name:json.dumps(next(feeds) if name=='vfinal-diagnostic.json' else {'next_gw':7}).encode())
    monkeypatch.setattr(api,'verify_official_now',lambda forecast:7)
    def compute(*args,**kwargs):
        calls.append(True)
        (tmp_path/'result.json').write_text('{"synthetic":true}')
        return type('Result',(),{'returncode':0})()
    monkeypatch.setattr(api.subprocess,'run',compute)
    with app.test_client() as c:
        r=c.post('/plans',json={'state':{'synthetic':'validation only'},'forecast_cutoff':'cutoff','forecast_sha256':forecast['forecast_sha256']},headers={'Origin':ORIGIN})
        receipt=r.get_json()
        try:
            assert calls==[True]
            result=c.get('/plans/'+receipt['id'],headers={'X-Plan-Key':receipt['key']})
            assert result.status_code==422
            assert result.get_json()['status']=='failed'
            assert 'synthetic' not in result.get_data(as_text=True)
            assert not (tmp_path/'input.json').exists()
        finally:jobs.pop(receipt['id'],None)
