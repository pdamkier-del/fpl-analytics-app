"""Per-cycle archive metadata index. Same pinned recovery and validation rules.

Avoid repeated O(all releases) find() calls when16origins are reread. No cache
survives a cycle; public assets remain verified by the unchanged C2hash checks.
"""
from types import SimpleNamespace
from archive_link import load_runtime as original_runtime


def indexed_backend(base):
    class IndexedGithub(base):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self._releases=None
            self._content={}

        def _index(self):
            if self._releases is None:
                found={};page=1
                while True:
                    rows=super().api(f'repos/{self.repository}/releases?per_page=100&page={page}')
                    for r in rows:found[r['tag_name']]=r
                    if len(rows)<100:break
                    page+=1
                self._releases=found
            return self._releases

        def find(self,tag):
            return self._index().get(tag)

        def create(self,tag,target):
            self._index()
            reply=super().create(tag,target)
            self._releases[tag]=reply
            return reply

        def upload(self,tag,path):
            super().upload(tag,path)
            release=self._index()[tag]
            self._releases[tag]=super().api(f'repos/{self.repository}/releases/{release["id"]}')

        def content(self,asset):
            # GitHubasset IDs identify immutable uploaded bodies, never latest names.
            key=(asset['id'],asset.get('digest'))
            if key not in self._content:self._content[key]=super().content(asset)
            return self._content[key]
    return IndexedGithub


def load_runtime(root):
    module,archive=original_runtime(root)
    return SimpleNamespace(Github=indexed_backend(module.Github),recover=module.recover),archive
