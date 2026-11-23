from pathlib import Path
from archive_link_v2 import indexed_backend


class FakeGithub:
    repository='test/repo'
    def __init__(self):
        self.calls=[];self.reads=0
        self.releases=[dict(id=i,tag_name=f'tag-{i}',assets=[])for i in range(101)]
    def api(self,path):
        self.calls.append(path)
        if '?per_page=100&page='in path:
            page=int(path.rsplit('=',1)[1]);return self.releases[(page-1)*100:page*100]
        return next(r for r in self.releases if r['id']==int(path.rsplit('/',1)[1]))
    def create(self,tag,target):
        r=dict(id=len(self.releases),tag_name=tag,assets=[]);self.releases.append(r);return r
    def upload(self,tag,path):
        old=next(r for r in self.releases if r['tag_name']==tag)
        new={**old,'assets':[dict(id=500,name=path.name)]}
        self.releases[self.releases.index(old)]=new
    def content(self,asset):self.reads+=1;return str(asset['id']).encode()


def test_release_index_is_once_per_cycle_and_writes_refresh_metadata():
    backend=indexed_backend(FakeGithub)()
    for i in range(101):assert backend.find(f'tag-{i}')['id']==i
    assert len(backend.calls)==2
    backend.create('new','commit');backend.upload('new',Path('record.json'))
    assert backend.find('new')['assets'][0]['id']==500
    assert len(backend.calls)==3
    assert indexed_backend(FakeGithub)()._releases is None


def test_asset_cache_is_per_identity_not_filename_and_not_persistent():
    backend=indexed_backend(FakeGithub)()
    first=dict(id=1,name='record.json',digest='sha256:a')
    assert backend.content(first)==backend.content(first)==b'1'
    assert backend.reads==1
    assert backend.content({**first,'id':2})==b'2'
    assert backend.reads==2
    backend.content({**first,'digest':'sha256:changed'})
    assert backend.reads==3
    assert indexed_backend(FakeGithub)()._content=={}


def test_v2_only_changes_archive_io_and_manifest_identity():
    root=Path(__file__).resolve().parents[1]
    baseline=(root/'run_online.py').read_text()
    candidate=(root/'run_online_v2.py').read_text()
    # Exact diff gate on the runner; score/selection/label logic is unchanged.
    expected=baseline.replace('"""Prospective frozen evaluation cycle. Before finality, never fetch live labels."""',
        '"""Prospective cycle v2: identical scores/selection, bounded archive metadata I/O."""')
    expected=expected.replace('from archive_link import load_runtime,candidate_issues,recover_verified',
        'from archive_link import candidate_issues,recover_verified\nfrom archive_link_v2 import load_runtime')
    expected=expected.replace('implementation-manifest.json','implementation-manifest.v2.json')
    assert candidate==expected
