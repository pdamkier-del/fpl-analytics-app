import sys,json,copy,gzip,os,time,threading
from pathlib import Path
from datetime import datetime,timezone,timedelta
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'analysis/followup-41-20261122/tests'));from test_private_ts_ledger import inputs
from evaluation_ops import ts_capture as cap
from evaluation_ops.private_routes import append_intention,append_reported_execution,register
from flask import Flask

def current_inputs():
 f,s,p,d,_=inputs();now=datetime.now(timezone.utc);f['data_asof']=(now-timedelta(minutes=2)).isoformat();f['origin_deadline']=(now+timedelta(days=1)).isoformat();s['observed_at']=(now-timedelta(minutes=1)).isoformat();p['computed_at']=now.isoformat();d['observed_at']=now.isoformat();f['forecast_sha256']=cap.ledger.sha(cap.ledger.canonical({k:v for k,v in f.items()if k!='forecast_sha256'}));p['forecast_sha256']=f['forecast_sha256'];p['manager_state_sha256']=cap.ledger.sha(cap.ledger.canonical(s));return f,s,p,d,now
@pytest.fixture
def store(tmp_path,monkeypatch):
 volume=tmp_path/'persistent';root=volume/'ts';root.mkdir(parents=True,mode=0o700);att={'mount_path':str(volume),'persistent':True,'private':True,'public_export':False,'backups_private':True,'operator_reference':'SYNTHETIC_TEST_VOLUME'};(root/'storage-attestation.json').write_text(json.dumps(att));(root/'storage-attestation.json').chmod(0o600);monkeypatch.setattr(cap.os.path,'ismount',lambda p:Path(p)==volume)
 for k in ['CI','GITHUB_ACTIONS']:monkeypatch.delenv(k,raising=False)
 monkeypatch.setenv('FPL_TS_PRIVATE_ROOT',str(root));monkeypatch.setenv('FPL_TS_PRIVATE_VOLUME',str(volume));return root

def test_unconfigured_storage_fails_closed(monkeypatch):
 f,s,p,d,now=current_inputs();monkeypatch.delenv('FPL_TS_PRIVATE_ROOT',raising=False);r=cap.after_success(f,s,p,now=now);assert r['status']=='not_captured'and r['reason_code']=='private_storage_unconfigured'

def test_capture_preserves_recommendation_without_inventing_intent(store):
 f,s,p,d,now=current_inputs();before=copy.deepcopy((f,s,p));r=cap.after_success(f,s,p,now=now);assert r['status']=='recorded_private';assert (f,s,p)==before;record=json.loads(gzip.decompress(next(store.glob('record-*')).read_bytes()));assert record['manager_decision']is None and record['executed_transfers']is None;assert record['capture_kind']=='recommendation_only';assert record['recommendation']['lineup']==p['lineup']

@pytest.mark.parametrize('case,code',[('CI','public_ci_forbidden'),('ephemeral','persistent_volume_unverified'),('permissions','private_permissions_invalid'),('attestation','storage_attestation_missing'),('late','deadline_passed'),('synthetic','validation_fixture_not_observation')])
def test_unsafe_capture_is_rejected_with_precise_nonprivate_reason(store,monkeypatch,case,code):
 f,s,p,d,now=current_inputs()
 if case=='CI':monkeypatch.setenv('GITHUB_ACTIONS','true')
 if case=='ephemeral':monkeypatch.setattr(cap.os.path,'ismount',lambda p:False)
 if case=='permissions':store.chmod(0o755)
 if case=='attestation':(store/'storage-attestation.json').unlink()
 if case=='late':now=cap.ledger.clock(f['origin_deadline'])
 if case=='synthetic':s['validation_only']=True
 r=cap.after_success(f,s,p,now=now);assert r['reason_code']==code;assert not list(store.glob('record-*'));assert str(store)not in json.dumps(r)

def test_intention_and_execution_are_separate_private_records(store):
 f,s,p,d,now=current_inputs();s['extra_metadata']='not a model input';p['manager_state_sha256']=cap.ledger.sha(cap.ledger.canonical(s));r=cap.after_success(f,s,p,now=now)
 assert append_intention(store,r['capture_id'],d,now=now)['kind']=='user_intention'
 execution=append_reported_execution(store,r['capture_id'],{'transfers':[]},now=cap.ledger.clock(f['origin_deadline'])+timedelta(seconds=1));assert execution['execution_verified']is False
 events=[json.loads(x.read_text())for x in(store/'observations').glob('*.json')];assert any(e['kind']=='reported_execution'and e['eligibility_for_realized_strategy_score']is False for e in events);original=json.loads(gzip.decompress(next(store.glob('record-*')).read_bytes()));assert original['manager_decision']is None

def test_private_event_route_reuses_capability(store,tmp_path):
 f,s,p,d,now=current_inputs();r=cap.after_success(f,s,p,now=now);jobdir=tmp_path/'job';jobdir.mkdir();(jobdir/'result.json').write_text(json.dumps({'evaluation_capture':r}));app=Flask('evaluation_test');jobs={'job':{'key':'private-capability','status':'completed','created':time.time(),'directory':jobdir}};register(app,jobs,threading.Lock(),'https://pdamkier-del.github.io',3600)
 with app.test_client()as c:
  assert c.post('/plans/job/evaluation-intent',json=d).status_code==403
  assert c.post('/plans/job/evaluation-intent',json=d,headers={'Origin':'https://pdamkier-del.github.io'}).status_code==404
  assert c.post('/plans/job/evaluation-intent',json=d,headers={'Origin':'https://pdamkier-del.github.io','X-Plan-Key':'private-capability'}).status_code==201
  bad=c.post('/plans/job/evaluation-intent',json={'secret':'DO_NOT_LEAK'},headers={'Origin':'https://pdamkier-del.github.io','X-Plan-Key':'private-capability'});assert bad.status_code==422 and 'DO_NOT_LEAK'not in bad.get_data(as_text=True)
