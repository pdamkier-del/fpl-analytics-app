import copy
from datetime import timedelta
import json
from pathlib import Path
import shutil
import pytest
import archive
import automatic
from releases import persist
from test_archive import FakeGithub, inputs, NOW, CONFIG, WITNESS

REPO='pdamkier-del/fpl-analytics-app'


def row(identifier=102,**changes):
    value=dict(id=identifier,created_at=(NOW-timedelta(minutes=10)).isoformat(),
               status='completed',head_repository={'full_name':REPO},
               head_branch='main',path=automatic.PATH)
    value.update(changes)
    return value


class Backend(FakeGithub):
    repository=REPO
    def __init__(self,root):
        super().__init__(root);self.rows=[row()];self.job_success=True
    def api(self,path):
        if path.startswith(f'repos/{REPO}/releases?'):
            value=self.find('unused');return [value]if value else[]
        if '/jobs?'in path:
            return {'jobs':[dict(name='current / current',status='completed',conclusion='success'if self.job_success else'failure')]}
        if '/artifacts?'in path:
            return {'artifacts':[dict(name=n,expired=False)for n in ['mm-current-live-preview','current-B-origin-input-evidence']]}
        if '/actions/workflows/'in path:
            assert 'branch=main'in path and 'status=completed'in path
            return {'workflow_runs':self.rows}
        if '/actions/runs/'in path:
            return next(r for r in self.rows if str(r['id'])==path.rsplit('/',1)[1])
        raise AssertionError(path)


def witness(identifier=102):
    return dict(WITNESS,repository=REPO,run_id=identifier)


def setup(tmp_path,**kw):
    current,sources,f,fixtures=inputs(tmp_path/'input',**kw)
    backend=Backend(tmp_path/'github')
    bootstrap=json.loads((sources/'bootstrap.json').read_text())
    def transport(repo,identifier,name,target):
        assert repo==REPO
        if name=='mm-current-live-preview':
            shutil.copytree(current,target/'current')
            # Files from artifacts are data; this code must never run.
            (target/'never_execute.py').write_text('raise RuntimeError("ARTIFACT_CODE_RAN")')
        else:
            shutil.copytree(sources,target/'work/current-B-inputs')
    def archiver(b,r,d,t,**kwargs):
        return automatic.archive_one(b,r,d,t,collector=lambda repo,identifier:witness(int(identifier)),transport=transport,**kwargs)
    return backend,bootstrap,current,sources,archiver,transport


def test_discover_new_original_archive_recover_then_no_write(tmp_path):
    backend,bootstrap,current,sources,archiver,_=setup(tmp_path)
    before=(current/'forecast.json').read_bytes()
    report=automatic.execute(backend,tmp_path/'status',archive.PIN,now=NOW,bootstrap=bootstrap,archiver=archiver)
    assert report['status']=='complete' and report['rows'][0]['status']=='archived_and_recovered'
    assert not report['model_recomputed']and not report['app_deployed']and not report['private_data_used']
    assert report['coverage']['next_origin_gw']==12 and report['coverage']['next_origin_archived']
    assets=copy.deepcopy(backend.find('')['assets'])
    repeat=automatic.execute(backend,tmp_path/'fresh-status',archive.PIN,now=NOW+timedelta(minutes=1),bootstrap=bootstrap,archiver=archiver)
    assert repeat['status']=='complete' and repeat['rows'][0]['status']=='already_archived_no_write'
    assert backend.find('')['assets']==assets and (current/'forecast.json').read_bytes()==before


@pytest.mark.parametrize('foreign',[{'head_branch':'feature'},{'head_repository':{'full_name':'evil/repo'}},{'path':'different.yml'}])
def test_foreign_workflow_or_branch_not_consumed(tmp_path,foreign):
    backend,bootstrap,_,_,_,_=setup(tmp_path);backend.rows=[row(**foreign)]
    report=automatic.execute(backend,tmp_path/'status',archive.PIN,now=NOW,bootstrap=bootstrap,
                             archiver=lambda *a,**k:pytest.fail('Must not consume foreign artifacts'))
    assert report['status']=='failed' and report['failures']
    assert backend.find('')is None


def test_producer_failure_visible_and_no_download(tmp_path):
    backend,bootstrap,_,_,archiver,_=setup(tmp_path);backend.job_success=False
    report=automatic.execute(backend,tmp_path/'status',archive.PIN,now=NOW,bootstrap=bootstrap,archiver=archiver)
    assert report['status']=='failed' and report['rows'][0]['status']=='producer_failed'
    assert not report['coverage']['next_origin_archived']and backend.find('')is None


def test_deadline_passed_rejected_before_any_release(tmp_path):
    backend,bootstrap,_,_,archiver,_=setup(tmp_path)
    out=tmp_path/'status';out.mkdir()
    result=archiver(backend,row(),out,archive.PIN,now=NOW+timedelta(days=2))
    assert result['status']=='late_rejected'and backend.find('')is None


def test_private_payload_not_exported_or_logged(tmp_path):
    backend,bootstrap,current,_,archiver,_=setup(tmp_path)
    f=json.loads((current/'forecast.json').read_text())
    f['manager_state']={'bank_tenths':999,'source':'SECRET_SENTINEL'}
    (current/'forecast.json').write_text(json.dumps(f))
    report=automatic.execute(backend,tmp_path/'status',archive.PIN,now=NOW,bootstrap=bootstrap,archiver=archiver)
    assert report['status']=='failed'and report['rows'][0]['status']=='archive_failed'
    assert backend.find('')is None and 'SECRET_SENTINEL'not in json.dumps(report)
    assert sorted(p.name for p in(tmp_path/'status').iterdir())==['status.json']


def test_missing_completed_and_next_gw_not_invented():
    events=[dict(id=11,deadline_time=(NOW-timedelta(days=3)).isoformat()),
            dict(id=12,deadline_time=(NOW-timedelta(hours=1)).isoformat()),
            dict(id=13,deadline_time=(NOW+timedelta(days=1)).isoformat())]
    status=automatic.coverage_status({},dict(events=events),NOW,NOW-timedelta(days=1))
    assert status['missing_completed_origins']==[12]
    assert status['next_origin_gw']==13 and not status['next_origin_archived']


def test_deleted_asset_is_not_silently_treated_as_valid(tmp_path):
    backend,bootstrap,current,sources,archiver,_=setup(tmp_path)
    first=automatic.execute(backend,tmp_path/'first',archive.PIN,now=NOW,bootstrap=bootstrap,archiver=archiver)
    assert first['status']=='complete'
    metadata=json.loads((backend.root/'metadata.json').read_text())
    metadata['assets']=[a for a in metadata['assets']if a['name']!='mm.json.gz']
    (backend.root/'metadata.json').write_text(json.dumps(metadata))
    _,coverage,errors,_=automatic.inventory(backend,NOW)
    assert errors and not coverage


def test_main_consumer_has_no_producer_deploy_or_private_dependency():
    root=archive.ROOT
    workflow=(root/'.github/workflows/public-forecast-archive.yml').read_text()
    assert 'workflow_run:'in workflow and 'schedule:'in workflow and 'branches: [main]'in workflow
    assert '43 * * * *'in workflow and 'cancel-in-progress: false'in workflow
    assert 'persist-credentials: false'in workflow
    for forbidden in ['pages: write','id-token: write','service/','evaluation_ops','workflow_call','source_ref:', 'uses: pdamkier-del/']:
        assert forbidden not in workflow
    for forbidden in ['preview-overlay.py','install_private_hook.py','ts_capture.py','contract-v1.js']:
        assert not list((root/'integration').rglob(forbidden))
