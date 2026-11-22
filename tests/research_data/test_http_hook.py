"""Exercise the real HTTP completion hook while stubbing only the numerical worker."""
import importlib.util,json,sys,types,os
from pathlib import Path
import pytest
from test_ts_capture import current_inputs,store
from evaluation_ops import ts_capture as cap
ROOT=Path(os.environ['FPL_CAPTURE_RUNTIME']) if os.environ.get('FPL_CAPTURE_RUNTIME') else None
pytestmark=pytest.mark.skipif(ROOT is None,reason='Set FPL_CAPTURE_RUNTIME to verified installed runtime')
@pytest.mark.parametrize('capture_enabled',[False,True])
def test_original_completion_hook_runs_after_checks_and_preserves_plan(tmp_path,monkeypatch,store,capture_enabled):
 spec=importlib.util.spec_from_file_location('evaluation_http_test',ROOT/'service/app.py');api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
 f,s,result,d,now=current_inputs();order=[];jobdir=tmp_path/'job';jobdir.mkdir()
 parent=types.ModuleType('scripts');parent.__path__=[];monkeypatch.setitem(sys.modules,'scripts',parent);monkeypatch.setitem(sys.modules,'scripts.b_snapshot_policy',types.SimpleNamespace(POLICY='known-snapshot-policy'));monkeypatch.setitem(sys.modules,'scripts.b_chain_contract',types.SimpleNamespace(VERSION='B-MM-PM-TS-v1'))
 class Immediate:
  def __init__(self,target,**kw):self.target=target
  def start(self):self.target()
 def public(path):return json.dumps(f if path!='current-players.json'else{'next_gw':12}).encode()
 def verified(*a,**kw):order.append('source_checked')
 real_run=api.subprocess.run
 def compute(args,**kw):
  if 'locked_numerical_runtime.py'in str(args):order.append('original_worker');(jobdir/'result.json').write_text(json.dumps(result));return types.SimpleNamespace(returncode=0)
  return real_run(args,**kw)
 original_capture=cap.after_success
 def observed(*a,**kw):order.append('capture');return original_capture(*a,**kw)
 monkeypatch.setattr(api,'original_runtime_ready',lambda:True);monkeypatch.setattr(api.threading,'Thread',Immediate);monkeypatch.setattr(api.tempfile,'mkdtemp',lambda **kw:str(jobdir));monkeypatch.setattr(api,'get_public',public);monkeypatch.setattr(api,'verify_official_now',verified);monkeypatch.setattr(api,'require_forecast_snapshot',lambda f,expected:f['forecast_sha256']);monkeypatch.setattr(api.subprocess,'run',compute);monkeypatch.setattr(cap,'after_success',observed)
 if not capture_enabled:monkeypatch.delenv('FPL_TS_PRIVATE_ROOT')
 with api.app.test_client()as c:
  receipt=c.post('/plans',json={'state':s,'forecast_cutoff':f['data_asof'],'forecast_sha256':f['forecast_sha256']},headers={'Origin':api.ORIGIN}).get_json();r=c.get('/plans/'+receipt['id'],headers={'X-Plan-Key':receipt['key']});assert r.status_code==200;got=r.get_json()['plan'];assert got['plan']==result['plan']and got['lineup']==result['lineup'];assert got['comparison']==result['comparison'];assert order==['source_checked','original_worker','source_checked','capture'];assert got['evaluation_capture']['status']==('recorded_private'if capture_enabled else'not_captured');assert not(jobdir/'input.json').exists()
