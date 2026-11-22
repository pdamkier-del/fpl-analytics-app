import copy
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
import archive
from releases import persist, recover

NOW=datetime.now(timezone.utc).replace(microsecond=0)
WITNESS=dict(schema='fpl-computation-witness/v1',numerical_source=archive.PIN,producer_started_at=(NOW-timedelta(minutes=10)).isoformat(),producer_completed_at=(NOW-timedelta(minutes=1)).isoformat(),clock_basis='SYNTHETIC_TEST_JOB')
CONFIG=json.loads((archive.ROOT/'integration/research-data/frozen-ts-config.json').read_text())


def inputs(base, *, blank_double=False):
    current=base/'current';sources=base/'sources'
    current.mkdir(parents=True);sources.mkdir()
    gws=list(range(12,18));players=[];mm=[];official=[]
    fixtures=[]
    for g in gws:
        count=0 if blank_double and g==12 else 2 if blank_double and g==14 else 1
        fixtures.extend(dict(id=g*10+j,event=g,finished=True,finished_provisional=True)for j in range(count))
    positions=[1]*2+[2]*5+[3]*5+[4]*3
    for pid,pos in enumerate(positions,1):
        weeks=[]
        for g in gws:
            matches=[]
            for fx in [r for r in fixtures if r['event']==g]:
                identity=f'live-2026-27-fpl-{fx["id"]}'
                matches.append(dict(fixture_uuid=identity,xpts=4.,xmins=90.,pm_analytic_minutes=90.))
                mm.append(dict(player_id=f'player-{pid}',fixture_id=identity,gw=g,xmins=90.))
            n=len(matches)
            weeks.append(dict(gw=g,xpts=4.*n,xmins=90.*n,pm_analytic_minutes=90.*n,
                              p_play=float(n>0),
                              fixtures=matches,scenarios=dict(points=[4.*n]*4,minutes=[90.*n]*4)))
        players.append(dict(id=pid,name=f'Synthetic {pid}',player_uuid=f'player-{pid}',position=pos,team_id=(pid-1)//3+1,price_tenths=50,weeks=weeks))
        official.append(dict(id=pid,team=(pid-1)//3+1,position=pos,price=5.))
    bootstrap=dict(events=[dict(id=12,deadline_time=(NOW+timedelta(days=1)).isoformat())],elements=[dict(id=p['id'],code=1000+p['id'],ep_next='4.0')for p in players])
    provenance=dict(fixtures_sha256=archive.sha(archive.canonical(fixtures)))
    for name,doc in [('bootstrap.json',bootstrap),('fixtures.json',fixtures),('provenance.json',provenance)]:
        (sources/name).write_bytes(archive.canonical(doc))
    f=dict(model='B-MM-PM-TS-v1',mm_version='B-MM-PM-TS-v1',season='2026-27',gws=gws,players=players,
           scope='prospective_preview',locked_model_active=False,
           minute_sampler_audit=dict(sampler='B-MM-PM-TS-v1',all_MM_to_PM_means_consistent=True),
           data_asof=(NOW-timedelta(minutes=2)).isoformat(),origin_deadline=bootstrap['events'][0]['deadline_time'],
           scenario_contract=dict(version='shared-PM-match-draws-v1',draws=4),
           code_sha256={'synthetic_source.py':'a'*64},input_sha256={n:archive.sha((sources/n).read_bytes())for n in ['bootstrap.json','provenance.json']})
    f['forecast_sha256']=archive.sha(archive.canonical(f))
    m=dict(model_version=f['model'],data_at=f['data_asof'],origin_deadline=f['origin_deadline'],players=mm)
    m['content_sha256']=archive.sha(json.dumps(m,sort_keys=True,separators=(',',':')).encode())
    c=dict(next_gw=12,players=official)
    for name,doc in [('forecast.json',f),('mm.json',m),('catalogue.json',c)]:
        (current/name).write_bytes(archive.canonical(doc))
    index=dict(model=f['model'],gws=gws,data_asof=f['data_asof'],origin_deadline=f['origin_deadline'],forecast_sha256=f['forecast_sha256'],forecast_file='forecast.json',mm_file='mm.json',catalogue_file='catalogue.json')
    for name,key in [('forecast.json','forecast_file_sha256'),('mm.json','mm_file_sha256'),('catalogue.json','catalogue_sha256')]:index[key]=archive.sha((current/name).read_bytes())
    (current/'index.json').write_bytes(archive.canonical(index))
    return current,sources,f,fixtures


def build(tmp_path, **kw):
    current,sources,f,fixtures=inputs(tmp_path/'input',**kw)
    folder=archive.bundle(current,tmp_path/'archive',CONFIG,sources=sources,computation=WITNESS,now=NOW)
    return folder,current,sources,f,fixtures


def test_restart_and_idempotency_preserve_original_bytes(tmp_path):
    folder,current,sources,f,fx=build(tmp_path)
    before={p.name:p.read_bytes()for p in folder.iterdir()}
    assert archive.bundle(current,folder.parent,CONFIG,sources=sources,computation=WITNESS,now=NOW+timedelta(minutes=1))==folder
    assert {p.name:p.read_bytes()for p in folder.iterdir()}==before
    assert gzip.decompress((folder/'forecast.json.gz').read_bytes())==(current/'forecast.json').read_bytes()
    code='import sys;from pathlib import Path;import archive;archive.verify(Path(sys.argv[1]))'
    subprocess.run([sys.executable,'-c',code,str(folder)],env={'PYTHONPATH':str(archive.ROOT/'integration/research-data')},check=True)


@pytest.mark.parametrize('problem',['late','missing','altered','private','horizon','config','source'])
def test_fail_closed_inputs(tmp_path,problem):
    current,sources,f,fx=inputs(tmp_path/'input');config=copy.deepcopy(CONFIG);now=NOW
    if problem=='late':now=archive.clock(f['origin_deadline'])
    if problem=='missing':(current/'mm.json').unlink()
    if problem=='altered':(current/'forecast.json').write_text('{}')
    if problem=='private':
        m=json.loads((current/'mm.json').read_text());m['manager_state']={'secret':'DO_NOT_PUBLISH'};(current/'mm.json').write_text(json.dumps(m))
    if problem=='horizon':
        f['gws'].pop();(current/'forecast.json').write_text(json.dumps(f))
    if problem=='config':config['beam_width']=21
    if problem=='source':(sources/'bootstrap.json').write_text('{}')
    with pytest.raises((ValueError,KeyError)):
        archive.bundle(current,tmp_path/'archive',config,sources=sources,computation=WITNESS,now=now)
    assert not list((tmp_path/'archive').glob('*/manifest.json'))


def test_new_revision_does_not_replace_old(tmp_path):
    folder,current,sources,f,fx=build(tmp_path)
    before=(folder/'forecast.json.gz').read_bytes()
    f['revision_note']='new original forecast issue'
    f['forecast_sha256']=archive.sha(archive.canonical({k:v for k,v in f.items()if k!='forecast_sha256'}))
    (current/'forecast.json').write_bytes(archive.canonical(f))
    index=json.loads((current/'index.json').read_text());index['forecast_sha256']=f['forecast_sha256'];index['forecast_file_sha256']=archive.sha((current/'forecast.json').read_bytes());(current/'index.json').write_bytes(archive.canonical(index))
    second=archive.bundle(current,folder.parent,CONFIG,sources=sources,computation=WITNESS,now=NOW)
    assert second!=folder and (folder/'forecast.json.gz').read_bytes()==before


def test_tampered_archive_is_rejected(tmp_path):
    folder,*_=build(tmp_path)
    (folder/'mm.json.gz').write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'):archive.verify(folder)


def test_blank_double_and_rearranged_fixture_match_final_events(tmp_path):
    folder,current,sources,f,fixtures=build(tmp_path,blank_double=True)
    actual=[dict(fixture=fx['id'],element=p['id'],minutes=90,total_points=4)for fx in fixtures for p in f['players']]
    events=[dict(id=g,finished=True,data_checked=True)for g in range(12,19)]
    fixtures[0]['event']=18 # Final result moved; preserve origin target separately.
    rows=archive.match_final(folder,fixtures,actual,events)
    assert len(rows)==90 and not any(r['forecast_target_gw']==12 for r in rows)
    assert sum(r['forecast_target_gw']==14 for r in rows)==30
    assert any(r['actual_event']==18 for r in rows)
    events[-1]['data_checked']=False
    with pytest.raises(ValueError,match='checked'):archive.match_final(folder,fixtures,actual,events)


class FakeGithub:
    """Filesystem-backed test double, never a real GitHub write."""
    def __init__(self,root):self.root=root;root.mkdir(exist_ok=True)
    def find(self,tag):
        p=self.root/'metadata.json'
        return json.loads(p.read_text())if p.exists()else None
    def create(self,tag,target):
        d=dict(id=1,tag_name=tag,published_at=NOW.isoformat(),draft=False,assets=[])
        (self.root/'metadata.json').write_text(json.dumps(d));return d
    def upload(self,tag,path):
        d=self.find(tag)
        assert path.name not in {a['name']for a in d['assets']}
        (self.root/path.name).write_bytes(path.read_bytes())
        d['assets'].append(dict(id=len(d['assets'])+1,name=path.name,state='uploaded',created_at=NOW.isoformat()))
        (self.root/'metadata.json').write_text(json.dumps(d))
    def content(self,asset):return (self.root/asset['name']).read_bytes()


def test_permanent_recovery_without_local_or_ci_artifacts(tmp_path):
    folder,*_=build(tmp_path);backend=FakeGithub(tmp_path/'github')
    proof=persist(folder,backend,archive.PIN,now=NOW)
    persist(folder,FakeGithub(backend.root),archive.PIN,now=NOW)
    shutil.rmtree(folder.parent)
    recovered,again=recover(proof['tag'],tmp_path/'recovered',FakeGithub(backend.root))
    assert proof==again and archive.verify(recovered)['revision_id']==proof['revision_id']
    (backend.root/'forecast.json.gz').write_bytes(b'tampered')
    with pytest.raises(ValueError):recover(proof['tag'],tmp_path/'second',backend)


def test_late_release_and_overwrite_are_rejected(tmp_path):
    folder,*_=build(tmp_path);backend=FakeGithub(tmp_path/'github')
    with pytest.raises(ValueError,match='Late'):persist(folder,backend,archive.PIN,now=NOW+timedelta(days=2))
    proof=persist(folder,backend,archive.PIN,now=NOW)
    (backend.root/'mm.json.gz').write_bytes(b'other')
    with pytest.raises(ValueError,match='overwrite'):persist(folder,backend,archive.PIN,now=NOW)
