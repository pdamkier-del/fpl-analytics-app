"""Actual frozen TS calculation; synthetic inputs only, mocked mount explicitly."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.parametrize('archived',[False,True])
def test_original_worker_capture_and_cold_process_recovery(tmp_path,archived):
    runtime=os.environ.get('FPL_CAPTURE_RUNTIME')
    if not runtime:
        pytest.skip('Set FPL_CAPTURE_RUNTIME to disposable verified installed runtime')
    volume=tmp_path/'synthetic-volume';root=volume/'ts';root.mkdir(parents=True,mode=0o700)
    att=dict(mount_path=str(volume),persistent=True,private=True,public_export=False,
             backups_private=True,operator_reference='SYNTHETIC_MOCK_MOUNT_NOT_OPERATIONAL')
    (root/'storage-attestation.json').write_text(json.dumps(att));(root/'storage-attestation.json').chmod(0o600)
    env=dict(os.environ,PYTHONPATH=os.pathsep.join([runtime,runtime+'/src',runtime+'/scripts',runtime+'/tests']),
             FPL_TS_PRIVATE_ROOT=str(root),FPL_TS_PRIVATE_VOLUME=str(volume),OPENBLAS_NUM_THREADS='1')
    for key in ['CI','GITHUB_ACTIONS']:env.pop(key,None)
    if archived:
        from test_archive import build,FakeGithub,NOW
        from releases import persist,recover
        import archive
        folder,current,sources,f,fixtures=build(tmp_path/'public')
        backend=FakeGithub(tmp_path/'synthetic-github')
        proof=persist(folder,backend,archive.PIN,now=NOW)
        env['FPL_TEST_ARCHIVED_BUNDLE']=str(recover(proof['tag'],tmp_path/'recovered-public',backend)[0])
    script='''
import copy,json,os,gzip
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from test_unified_b_chain import unified_fixture
from service.preview_manager_job import calculate
from evaluation_ops.ts_capture import after_success,ledger,runtime_identity
f,s=unified_fixture();s['bank_tenths']=50
if os.environ.get('FPL_TEST_ARCHIVED_BUNDLE'):
 f=json.loads(gzip.decompress((Path(os.environ['FPL_TEST_ARCHIVED_BUNDLE'])/'forecast.json.gz').read_bytes()))
 s['gw']=f['gws'][0];s['observed_at']=(ledger.clock(f['data_asof'])-timedelta(minutes=1)).isoformat()
before=copy.deepcopy((f,s));result=calculate(f,s);original=copy.deepcopy(result)
assert result['current_team']['expected_score']==(48. if os.environ.get('FPL_TEST_ARCHIVED_BUNDLE') else 47.6)
with patch('evaluation_ops.ts_capture.os.path.ismount',lambda p:Path(p)==Path(os.environ['FPL_TS_PRIVATE_VOLUME'])):
 reply=after_success(f,s,result)
assert reply['status']=='recorded_private',reply
assert (f,s)==before and result==original
root=Path(os.environ['FPL_TS_PRIVATE_ROOT']);assert ledger.verify(root)==1
record=json.loads(ledger.gzip.decompress(next(root.glob('record-*')).read_bytes()))
assert ledger.canonical(record['original_model_output'])==ledger.canonical(original) and record['original_manager_input']==s
assert len(record['recommendation']['plan']['path'])==6
assert record['manager_decision']is None and record['executed_transfers']is None
assert record['price_snapshot'][0]['selling_price_tenths']==49
assert record['runtime_provenance']['numerical_sources_unchanged'] is True
assert len(runtime_identity()['files'])==537
print(json.dumps({'actual_frozen_worker':True,'private_records':1,'synthetic_input':True,'mount':'mocked_not_operational','original_output_unchanged':True}))
'''
    computed=subprocess.run([sys.executable,'-c',script],cwd=runtime,env=env,capture_output=True,text=True)
    assert computed.returncode==0,computed.stderr+computed.stdout
    # A new interpreter loads only the persisted ledger, no model recomputation.
    recovered=subprocess.run([sys.executable,'-c',
        'import os;from evaluation_ops.ts_capture import ledger;assert ledger.verify(os.environ["FPL_TS_PRIVATE_ROOT"])==1'],
        cwd=runtime,env=env,capture_output=True,text=True)
    assert recovered.returncode==0,recovered.stderr
    assert 'SYNTHETIC'not in computed.stdout and 'bank_tenths'not in computed.stdout
    if archived:
        actual=[dict(fixture=fx['id'],element=p['id'],total_points=4,minutes=90)for fx in fixtures for p in f['players']]
        events=[dict(id=g,finished=True,data_checked=True)for g in f['gws']]
        matched=archive.match_final(Path(env['FPL_TEST_ARCHIVED_BUNDLE']),fixtures,actual,events)
        assert len(matched)==90 and all(r['forecast']['xpts']==r['actual']['total_points']for r in matched)
