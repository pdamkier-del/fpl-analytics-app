"""Write-once GitHub Release persistence. No Pages deployment or private data."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import tempfile
from archive import canonical, clock, require, sha, verify


class Github:
    def __init__(self, repository):
        require(re.fullmatch(r'[\w.-]+/[\w.-]+',repository), 'Invalid repository')
        self.repository=repository

    def api(self, path, body=None, binary=False):
        args=['gh','api',path]
        if binary:
            args+=['-H','Accept: application/octet-stream']
        if body is not None:
            args+=['--method','POST','--input','-']
        result=subprocess.run(args,input=canonical(body) if body is not None else None,capture_output=True)
        # Never expose credentials from signed redirect errors in logs/receipts.
        if result.returncode:
            raise RuntimeError('GitHub request failed; inspect permissions/network without exporting credentials')
        return result.stdout if binary else json.loads(result.stdout)

    def find(self, tag):
        # Listing avoids treating permission/network errors as a missing release.
        page=1
        while True:
            rows=self.api(f'repos/{self.repository}/releases?per_page=100&page={page}')
            for r in rows:
                if r['tag_name']==tag:
                    return self.api(f'repos/{self.repository}/releases/{r["id"]}')
            if len(rows)<100:
                return None
            page+=1

    def create(self, tag, target):
        return self.api(f'repos/{self.repository}/releases',dict(
            tag_name=tag,target_commitish=target,name=tag,draft=False,prerelease=True,
            body='Original public MM/PM research snapshot. No manager data. Checksummed immutable revision; no model promotion or app deployment.'))

    def upload(self, tag, path):
        result=subprocess.run(['gh','release','upload',tag,str(path),'--repo',self.repository],capture_output=True)
        if result.returncode:
            raise RuntimeError('Release upload failed; no clobber/overwrite attempted')

    def content(self, asset):
        return self.api(f'repos/{self.repository}/releases/assets/{asset["id"]}',binary=True)


def persist(folder, backend, target, *, now=None):
    """Idempotent repair of missing assets only, never overwrite differing bytes."""
    manifest=verify(folder)
    require(re.fullmatch('[a-f0-9]{40}',target), 'Source target must be a full commit')
    tag=f'fpl-forecast-{manifest["season"]}-gw{manifest["origin_gw"]:02}-{manifest["revision_id"]}'
    release=backend.find(tag)
    if release is None:
        require((now or datetime.now(timezone.utc))<clock(manifest['official_deadline']), 'Late publication cannot become prospective')
        release=backend.create(tag,target)
    expected={'manifest.json':sha((folder/'manifest.json').read_bytes()),**manifest['files']}
    require(release['tag_name']==tag and not release.get('draft'), 'Wrong release')
    assets={a['name']:a for a in release.get('assets',[])}
    require(len(assets)==len(release.get('assets',[])) and not (set(assets)-set(expected)-{'publication.json'}), 'Unexpected release assets')
    for name,h in expected.items():
        if name not in assets:
            require((now or datetime.now(timezone.utc))<clock(manifest['official_deadline']), 'Incomplete release after deadline; not eligible')
            backend.upload(tag,folder/name)
        else:
            require(sha(backend.content(assets[name]))==h, 'Existing permanent asset differs; refusing overwrite')
    release=backend.find(tag)
    assets={a['name']:a for a in release['assets']}
    for name,h in expected.items():
        require(name in assets and assets[name].get('state')=='uploaded', 'Incomplete release')
        require(sha(backend.content(assets[name]))==h, 'Permanent recovery checksum failed')
        require(clock(manifest['data_cutoff'])<=clock(assets[name]['created_at'])<clock(manifest['official_deadline']), 'Asset published outside eligible issue window')
    published=max([clock(release['published_at']),*(clock(assets[n]['created_at']) for n in expected)])
    require(published<clock(manifest['official_deadline']), 'Release not published before deadline')
    proof=dict(schema='fpl-publication-receipt/v1',revision_id=manifest['revision_id'],
               forecast_sha256=manifest['forecast_sha256'],tag=tag,release_id=release['id'],
               publication_at=published.isoformat(),official_deadline=manifest['official_deadline'],
               assets={n:dict(id=assets[n]['id'],sha256=h,created_at=assets[n]['created_at']) for n,h in expected.items()},
               eligibility='original_predeadline_publication',private_data=False)
    if 'publication.json' in assets:
        require(backend.content(assets['publication.json'])==canonical(proof), 'Publication receipt differs')
    else:
        require((now or datetime.now(timezone.utc))<clock(manifest['official_deadline']), 'No eligible completion receipt before deadline')
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'publication.json';p.write_bytes(canonical(proof));backend.upload(tag,p)
    final=backend.find(tag)
    receipt=next(a for a in final['assets'] if a['name']=='publication.json')
    require(receipt.get('state')=='uploaded' and clock(receipt['created_at'])<clock(manifest['official_deadline']), 'Publication receipt completed too late')
    require(backend.content(receipt)==canonical(proof), 'Publication receipt recovery failed')
    return proof


def recover(tag, destination, backend):
    """Recover without CI artifacts; verify the original release and every byte."""
    release=backend.find(tag)
    require(release is not None, 'Permanent release unavailable')
    assets={a['name']:a for a in release['assets']}
    require('manifest.json' in assets and 'publication.json' in assets, 'Incomplete archive, not research eligible')
    raw=backend.content(assets['manifest.json']);manifest=json.loads(raw)
    expected_tag=f'fpl-forecast-{manifest["season"]}-gw{manifest["origin_gw"]:02}-{manifest["revision_id"]}'
    require(tag==expected_tag and re.fullmatch('[a-f0-9]{64}',manifest['revision_id']), 'Wrong revision tag')
    destination.mkdir(parents=True,exist_ok=True)
    folder=destination/manifest['revision_id']
    if not folder.exists():
        with tempfile.TemporaryDirectory(dir=destination) as temp:
            stage=Path(temp)/'bundle';stage.mkdir()
            (stage/'manifest.json').write_bytes(raw)
            for name in manifest['files']:
                require(Path(name).name==name and name in assets, 'Missing/unsafe archived filename')
                (stage/name).write_bytes(backend.content(assets[name]))
            verify(stage)
            stage.rename(folder)
    require((folder/'manifest.json').read_bytes()==raw, 'Local archive differs')
    # Existing release only; no creation/upload can occur in this completed path.
    proof=persist(folder,backend,manifest['model_source'])
    return folder,proof


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('folder',type=Path);p.add_argument('--repository',required=True)
    p.add_argument('--target',required=True)
    args=p.parse_args()
    proof=persist(args.folder,Github(args.repository),args.target)
    print(json.dumps({'status':'verified_permanent_public_archive','revision_id':proof['revision_id'],'tag':proof['tag'],'publication_at':proof['publication_at']}))
