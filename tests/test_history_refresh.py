"""Official history refresh is private, origin-bound and atomic on source failure."""
import time
import service.app as api
from scripts import export_fpl_team_history as export


def test_history_job_origin_input_capability_and_source_failure(monkeypatch):
    monkeypatch.setattr(export,'collect',lambda entry,season: {'entry_id':entry,'season':season,'weeks':[]})
    import service.history_job as worker
    monkeypatch.setattr(worker,'refresh',lambda directory,entry,season,get_public:export.collect(entry,season))
    with api.app.test_client() as c:
        assert c.post('/preview/history',json={}).status_code==403
        assert c.options('/preview/history',headers={'Origin':api.ORIGIN}).status_code==204
        for bad in [True,'123',-1,0,1000000000]:
            assert c.post('/preview/history',json={'entry_id':bad,'season':'2026-27'},headers={'Origin':api.ORIGIN}).status_code==400
        r=c.post('/preview/history',json={'entry_id':123,'season':'2026-27'},headers={'Origin':api.ORIGIN})
        assert r.status_code==202
        receipt=r.get_json();identifier=receipt['id']
        try:
            assert c.get('/plans/'+identifier).status_code==404
            for _ in range(100):
                r=c.get('/plans/'+identifier,headers={'X-Plan-Key':receipt['key']})
                if r.get_json()['status']!='running':break
                time.sleep(.01)
            assert r.get_json()['history']['entry_id']==123
            assert 'plan' not in r.get_json()
            assert r.headers['Cache-Control']=='no-store'
        finally:
            import shutil
            shutil.rmtree(api.jobs[identifier]['directory']);del api.jobs[identifier]
        def fail(*args):raise RuntimeError('private upstream details')
        monkeypatch.setattr(export,'collect',fail)
        r=c.post('/preview/history',json={'entry_id':123,'season':'2026-27'},headers={'Origin':api.ORIGIN})
        receipt=r.get_json();identifier=receipt['id']
        try:
            for _ in range(100):
                r=c.get('/plans/'+identifier,headers={'X-Plan-Key':receipt['key']})
                if r.status_code!=200 or r.get_json()['status']!='running':break
                time.sleep(.01)
            assert r.status_code==422
            assert 'private upstream' not in r.get_data(as_text=True)
        finally:
            shutil.rmtree(api.jobs[identifier]['directory']);del api.jobs[identifier]


def test_history_refresh_capacity_keeps_existing_compute(monkeypatch,tmp_path):
    api.jobs['existing']={'created':time.time(),'status':'running','directory':tmp_path,'key':'secret'}
    try:
        with api.app.test_client() as c:
            assert c.post('/preview/history',json={'entry_id':123,'season':'2026-27'},headers={'Origin':api.ORIGIN}).status_code==429
            assert len(api.jobs)==1
    finally:del api.jobs['existing']


def test_collector_checks_season_and_finality(monkeypatch):
    seen=[]
    def source(path):
        seen.append(path)
        if path=='bootstrap-static/':return {'events':[{'id':1,'deadline_time':'2026-08-21T12:00:00Z','finished':True,'data_checked':False}]}
        if path.endswith('transfers/'):return []
        if path.endswith('history/'):return {'current':[{'event':1}]}
        return {'picks':[], 'entry_history':{'event':1,'points':4}}
    monkeypatch.setattr(export,'get',source)
    import pytest
    with pytest.raises(ValueError,match='sæson'):export.collect(123,'2025-26')
    assert not any('/event/' in path for path in seen)
    data=export.collect(123,'2026-27')
    assert data['weeks'][0]['final'] is False
    assert data['schema']=='fpl-official-entry-history-v1'
