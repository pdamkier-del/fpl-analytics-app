"""Bridge to PR53's existing immutable archive. No second forecast collector."""
from datetime import datetime,timedelta,timezone
import gzip
import hashlib
import importlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
TAG=re.compile(r'fpl-forecast-(\d{4}-\d{2})-gw(\d{2})-([a-f0-9]{64})')


def load_runtime(root):
    expected=json.loads((HERE/'archive-source-hashes.json').read_text())
    commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    if commit!=expected['commit']:raise ValueError('C2 archive checkout is not pinned')
    for path,h in expected['files'].items():
        if hashlib.sha256((root/path).read_bytes()).hexdigest()!=h:raise ValueError('C2 archive helper changed')
    sys.path.insert(0,str(root/'integration/research-data'))
    module=importlib.import_module('releases');archive=importlib.import_module('archive')
    if not Path(module.__file__).resolve().is_relative_to(root.resolve()):raise ValueError('Unexpected archive import')
    return module,archive


def documents(folder):
    return {name:json.loads(gzip.decompress((folder/(name+'.gz')).read_bytes()))for name in
            ['forecast.json','mm.json','index.json','catalogue.json','official-bootstrap.json','official-fixtures.json','official-provenance.json']}


def recover_verified(runtime,backend,tag,destination):
    releases,archive=runtime
    folder,proof=releases.recover(tag,destination,backend)
    manifest=archive.verify(folder);docs=documents(folder)
    with tempfile.TemporaryDirectory()as temp:
        current=Path(temp)/'current';source=Path(temp)/'source';current.mkdir();source.mkdir()
        for name in ['forecast.json','mm.json','index.json','catalogue.json']:
            (current/name).write_bytes(gzip.decompress((folder/(name+'.gz')).read_bytes()))
        for name in ['bootstrap.json','fixtures.json','provenance.json']:
            (source/name).write_bytes(gzip.decompress((folder/('official-'+name+'.gz')).read_bytes()))
        archive.validate(current,json.loads((folder/'ts-config.json').read_bytes()),sources=source,
            computation=json.loads((folder/'computation-receipt.json').read_bytes()),
            now=archive.clock(manifest['captured_at']),model_commit=manifest['model_source'])
    return folder,manifest,proof,docs


def candidate_issues(runtime,backend,boundary,now):
    _,archive=runtime;rows=[];page=1
    while True:
        releases=backend.api(f'repos/{backend.repository}/releases?per_page=100&page={page}')
        for release in releases:
            match=TAG.fullmatch(release.get('tag_name',''))
            if not match or int(match[2])<12:continue
            assets={a['name']:a for a in release['assets']}
            if 'manifest.json'not in assets or 'publication.json'not in assets:continue
            manifest=json.loads(backend.content(assets['manifest.json']))
            if manifest.get('season')!='2026-27' or match[1]!='2026-27':continue
            issued=archive.clock(manifest['data_cutoff'])
            if issued<=boundary or manifest.get('model_source')!='161b67b6fb8786a38e78c245b92a03ad841575d8':continue
            complete=max(archive.clock(release['published_at']),*(archive.clock(a['created_at'])for a in assets.values()))
            cutoff=archive.clock(manifest['official_deadline'])-timedelta(minutes=60)
            if complete>cutoff or complete<=boundary:continue
            rows.append(dict(tag=release['tag_name'],revision_id=manifest['revision_id'],
                forecast_sha256=manifest['forecast_sha256'],gw=manifest['origin_gw'],season=manifest['season'],
                data_asof=manifest['data_cutoff'],completed_publication_at=complete.isoformat(),
                official_deadline=manifest['official_deadline'],selection_cutoff=cutoff.isoformat(),
                selection_ready=now>=cutoff))
        if len(releases)<100:break
        page+=1
    return sorted(rows,key=lambda r:(r['gw'],r['data_asof'],r['completed_publication_at'],r['revision_id']))
