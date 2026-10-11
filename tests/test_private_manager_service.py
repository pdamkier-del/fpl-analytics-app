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
        response=c.post('/plans',json={'state':{},'forecast_cutoff':'test'},headers={'Origin':ORIGIN})
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
