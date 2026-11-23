from datetime import timedelta
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from fixtures import NOW
from archive_link import candidate_issues,load_runtime


def test_original_issue_boundary_cutoff_and_latest_revision_are_outcome_blind():
    boundary=NOW-timedelta(days=1);deadline=NOW+timedelta(days=1);cutoff=deadline-timedelta(minutes=60)
    class Backend:
        repository='pdamkier-del/fpl-analytics-app'
        docs={}
        def api(self,path):return self.rows
        def content(self,asset):return json.dumps(self.docs[asset['id']]).encode()
    backend=Backend();backend.rows=[]
    cases=[('a',NOW-timedelta(hours=1),cutoff-timedelta(hours=2)),
           ('b',NOW,cutoff-timedelta(hours=1)),
           ('c',NOW,cutoff+timedelta(seconds=1)),
           ('d',boundary-timedelta(seconds=1),cutoff-timedelta(hours=1))]
    for i,(name,issued,published)in enumerate(cases):
        key=i+1;backend.docs[key]=dict(model_source='161b67b6fb8786a38e78c245b92a03ad841575d8',
            data_cutoff=issued.isoformat(),official_deadline=deadline.isoformat(),origin_gw=12,season='2026-27',
            forecast_sha256=name*64,revision_id=name*64)
        backend.rows.append(dict(tag_name='fpl-forecast-2026-27-gw12-'+name*64,published_at=published.isoformat(),
            assets=[dict(name='manifest.json',id=key,created_at=published.isoformat()),
                    dict(name='publication.json',id=key,created_at=published.isoformat())]))
    runtime=(None,SimpleNamespace(clock=lambda s:__import__('datetime').datetime.fromisoformat(s)))
    provisional=candidate_issues(runtime,backend,boundary,NOW)
    assert [r['revision_id'][0]for r in provisional]==['a','b']
    assert not any(r['selection_ready']for r in provisional)
    ready=candidate_issues(runtime,backend,boundary,deadline)
    assert ready[-1]['revision_id']=='b'*64 and all(r['selection_ready']for r in ready)


def test_archive_helpers_are_pinned_existing_implementation():
    path=Path(os.environ.get('FPL_ARCHIVE_RUNTIME','/workspace/work/fpl-c1-archive-runtime'))
    if not path.exists():pytest.skip('Pinned archive checkout is supplied by the research workflow')
    release,archive=load_runtime(path)
    assert archive.PIN=='161b67b6fb8786a38e78c245b92a03ad841575d8'
    assert Path(release.__file__).resolve().is_relative_to(path)
