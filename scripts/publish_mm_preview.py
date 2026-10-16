#!/usr/bin/env python3
"""Overlay ONLY mm-preview on the latest successful production Pages artifact.

Run under the existing fpl-pages-publication concurrency lock. Reuse the exact
published site, never execute PM/TS or rebuild production assets for a preview.
Persist the public historical preview path to the live branch for later builds.
"""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,tarfile,zipfile
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
REPO='pdamkier-del/fpl-analytics-app'
WORK=ROOT/'work/mm-preview-publication'
SITE=ROOT/'.mm-preview-site'

def gh(path):
    return json.loads(subprocess.check_output(['gh','api','repos/'+REPO+'/'+path],text=True))
def hashes(folder):
    return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file() and not p.relative_to(folder).parts[0]=='mm-preview'}
def main():
    WORK.mkdir(parents=True,exist_ok=True)
    runs=gh('actions/runs?status=success&per_page=100')['workflow_runs']
    allowed={' .github/workflows/free-pages.yml'.strip(),'.github/workflows/current-diagnostic-forecast.yml'}
    candidates=sorted([r for r in runs if r['path'] in allowed],key=lambda r:r['updated_at'],reverse=True)
    artifact=None;run=None
    for r in candidates:
        arts=gh('actions/runs/'+str(r['id'])+'/artifacts')['artifacts']
        good=[a for a in arts if not a['expired'] and a['name'].startswith('github-pages-')]
        if good:artifact=good[0];run=r;break
    if artifact is None:raise ValueError('No verified production Pages artifact; refusing to rebuild/replace production')
    archive=WORK/'production-pages.zip'
    with archive.open('wb') as out:subprocess.run(['gh','api','repos/'+REPO+'/actions/artifacts/'+str(artifact['id'])+'/zip'],stdout=out,check=True)
    with zipfile.ZipFile(archive) as z:
        if z.namelist()!=['artifact.tar']:raise ValueError('Unexpected Pages archive')
        z.extract('artifact.tar',WORK)
    SITE.mkdir(parents=True,exist_ok=True)
    with tarfile.open(WORK/'artifact.tar') as tar:tar.extractall(SITE,filter='data')
    before=hashes(SITE)
    if not before or 'vfinal-diagnostic.json' not in before:raise ValueError('Invalid production artifact')
    # Verify the artifact really matches the currently served forecast.
    with urlopen('https://pdamkier-del.github.io/fpl-analytics-app/vfinal-diagnostic.json',timeout=60) as r:live=json.load(r)
    frozen=json.loads((SITE/'vfinal-diagnostic.json').read_text())
    for k in ['data_asof','checksums','gws','model']:
        if live.get(k)!=frozen.get(k):raise ValueError('Production publication changed; rerun preview against newest artifact')
    source=ROOT/'app/mm-preview';dest=SITE/'mm-preview'
    if dest.exists():shutil.rmtree(dest)
    shutil.copytree(source,dest)
    after=hashes(SITE)
    if before!=after:raise ValueError('Preview altered a production file')
    evidence=dict(preview_source_commit=os.environ['GITHUB_SHA'],production_run=run['id'],production_artifact=artifact['id'],production_files=len(before),production_files_identical=True,locked_model_active=False,preview_scope='historical_replay',production_sha256=before)
    (dest/'publication.json').write_text(json.dumps(evidence,sort_keys=True,indent=2)+'\n')
    # Keep this isolated new path in future normal forecast publications. No
    # production scripts, model files or existing web assets enter this commit.
    livework=WORK/'live'
    subprocess.run(['git','fetch','origin','free-github-static-20261010'],cwd=ROOT,check=True)
    subprocess.run(['git','worktree','add','--detach',str(livework),'FETCH_HEAD'],cwd=ROOT,check=True)
    destination=livework/'app/mm-preview'
    if destination.exists():shutil.rmtree(destination)
    shutil.copytree(dest,destination)
    subprocess.run(['git','config','user.name','FPL MM preview publisher'],cwd=livework,check=True)
    subprocess.run(['git','config','user.email','mm-preview@users.noreply.github.com'],cwd=livework,check=True)
    subprocess.run(['git','add','app/mm-preview'],cwd=livework,check=True)
    subprocess.run(['git','commit','-m','Publish isolated historical MM integration preview [skip ci]'],cwd=livework,check=True)
    subprocess.run(['git','push','origin','HEAD:free-github-static-20261010'],cwd=livework,check=True)
    print(json.dumps({k:v for k,v in evidence.items() if k!='production_sha256'},indent=2))
if __name__=='__main__':main()
