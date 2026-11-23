import copy
from datetime import timedelta
import json
from pathlib import Path
import pytest
from fixtures import fixture,NOW
from labels import digest
from store import get_record,put_record
import run_online as online


class MemoryBackend:
    repository='pdamkier-del/fpl-analytics-app'
    def __init__(self):self.releases={};self.bodies={}
    def find(self,tag):return self.releases.get(tag)
    def create(self,tag,target):
        assert tag not in self.releases
        r=dict(id=len(self.releases)+1,tag_name=tag,published_at=NOW.isoformat(),assets=[])
        self.releases[tag]=r;return r
    def upload(self,tag,path):
        r=self.releases[tag]
        assert not r['assets']
        asset=dict(id=len(self.bodies)+1,name='record.json',created_at=NOW.isoformat())
        self.bodies[asset['id']]=path.read_bytes();r['assets'].append(asset)
    def content(self,asset):return self.bodies[asset['id']]
    def api(self,path):return list(self.releases.values())


def setup(monkeypatch,tmp_path):
    f,m,b,fx,p,ids,h=fixture()
    here=tmp_path/'implementation';here.mkdir()
    (here/'PROTOCOL.md').write_text('synthetic fixed protocol')
    boundary=dict(registered_at=(NOW-timedelta(hours=2)).isoformat(),event_sha256='b'*64)
    (here/'registration-boundary.json').write_text(json.dumps(boundary))
    (here/'implementation-manifest.json').write_text('{"synthetic":true}')
    monkeypatch.setattr(online,'HERE',here)
    issue=dict(tag='original-public-forecast',revision_id='a'*64,forecast_sha256=f['forecast_sha256'],
               gw=12,season=f['season'],data_asof=f['data_asof'],completed_publication_at=NOW.isoformat(),
               official_deadline=b['events'][11]['deadline_time'],selection_cutoff=(NOW+timedelta(hours=23)).isoformat(),selection_ready=True)
    docs={'forecast.json':f,'mm.json':m,'official-bootstrap.json':b,'official-fixtures.json':fx}
    monkeypatch.setattr(online,'recover_verified',lambda *a,**k:(tmp_path,dict(revision_id=issue['revision_id']),{'original':True},docs))
    monkeypatch.setattr(online,'candidate_issues',lambda *a,**k:[copy.deepcopy(issue)])
    labels=dict(status='final',payload=p,identities=ids,history=[dict(id=pid,fixture=fixture,stats=v)for(pid,fixture),v in h.items()])
    return MemoryBackend(),issue,labels,here


def test_record_is_private_safe_write_once_and_cold_recoverable(tmp_path):
    b=MemoryBackend();data=dict(original='public',value=1)
    assert put_record(b,'research-selection',data,'a'*40)==data
    assert get_record(b,'research-selection')==data
    with pytest.raises(ValueError,match='immutable'):put_record(b,'research-selection',dict(value=2),'a'*40)
    with pytest.raises(ValueError,match='Private'):put_record(b,'bad',dict(manager_state={'bank_tenths':1}),'a'*40)
    assert 'bad'not in b.releases
    b.bodies[1]=b.bodies[1].replace(b'"value":1',b'"value":2')
    with pytest.raises(ValueError,match='changed'):get_record(b,'research-selection')


def test_pending_selection_does_not_request_any_outcomes(monkeypatch,tmp_path):
    b,issue,labels,here=setup(monkeypatch,tmp_path)
    monkeypatch.setattr(online,'candidate_issues',lambda *a,**k:[{**issue,'selection_ready':False}])
    result=online.cycle(None,b,tmp_path,'a'*40,now=NOW,fetcher=lambda f:pytest.fail('No labels before selection'))
    assert result['status']=='awaiting_selection_cutoff'and result['scores_prospective']==0
    assert b.releases=={}


def test_pending_finality_creates_selection_not_a_score(monkeypatch,tmp_path):
    b,issue,labels,here=setup(monkeypatch,tmp_path)
    calls=[]
    def pending(f):
        assert get_record(b,online.STUDY+'-selection-gw12')==issue
        calls.append('finality_only');return {'status':'awaiting_results'}
    result=online.cycle(None,b,tmp_path,'a'*40,now=NOW+timedelta(days=2),publish=True,fetcher=pending)
    assert result['scores_prospective']==0 and calls==['finality_only']
    assert result['rows'][0]['status']=='awaiting_results'
    assert not any('-report-'in t for t in b.releases)


def test_two_final_label_revisions_preserve_forecast_and_all_reports(monkeypatch,tmp_path):
    b,issue,labels,here=setup(monkeypatch,tmp_path);before=copy.deepcopy(issue)
    a=online.cycle(None,b,tmp_path,'a'*40,now=NOW+timedelta(days=4),publish=True,fetcher=lambda f:labels)
    assert a['scores_prospective']==1 and a['cumulative']['mm_start_comparison']['status']=='not_inferential'
    first=[t for t in b.releases if'-report-'in t]
    again=online.cycle(None,b,tmp_path,'a'*40,now=NOW+timedelta(days=5),publish=True,fetcher=lambda f:labels)
    assert first==[t for t in b.releases if'-report-'in t]
    revised=copy.deepcopy(labels);revised['payload']['official_player_live'][0]['stats']['bps']=11
    revised['history'][0]['stats']['bps']=11
    # BPS label correction changes the observed label revision, not point means.
    online.cycle(None,b,tmp_path,'a'*40,now=NOW+timedelta(days=6),publish=True,fetcher=lambda f:revised)
    assert len([t for t in b.releases if'-report-'in t])==2
    assert get_record(b,online.STUDY+'-selection-gw12')==before


def test_after_fixed_lock_no_new_label_request_can_affect_primary(monkeypatch,tmp_path):
    b,issue,labels,here=setup(monkeypatch,tmp_path)
    online.cycle(None,b,tmp_path,'a'*40,now=NOW+timedelta(days=4),publish=True,fetcher=lambda f:labels)
    window=get_record(b,online.STUDY+'-window')
    final=online.cycle(None,b,tmp_path,'a'*40,now=online.instant(window['data_lock_at'])+timedelta(days=1),publish=True,
        fetcher=lambda f:pytest.fail('No fresh outcomes after fixed lock'))
    assert final['status']=='final_inconclusive'
    again=online.cycle(None,b,tmp_path,'a'*40,now=NOW+timedelta(days=300),publish=True,
        fetcher=lambda f:pytest.fail('No later peeking'))
    assert again['status']=='final_primary_already_locked'


def test_future_dated_label_is_rejected(monkeypatch,tmp_path):
    b,issue,labels,here=setup(monkeypatch,tmp_path)
    result=online.cycle(None,b,tmp_path,'a'*40,now=NOW+timedelta(days=2),publish=True,fetcher=lambda f:labels)
    assert result['status']=='blocked_or_partial_labels'and result['scores_prospective']==0
    assert result['rows'][0]['status']=='blocked_origin'
