"""Reuse the existing public publication mirror, with old/new byte recovery.

No Release/tag permission is needed. No new collection system or model calls.
Only validated public data and the already-approved isolated preview are indexed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile

from reviewed_baseline import PREFIX, REVIEW
from refresh_data import REPO, canonical, data_path, read, validate_candidate

MIRROR='free-github-static-20261010'
URL='https://github.com/'+REPO+'.git'
DATA_ROOTS=['app/mm-preview/current','app/mm-preview/gk','app/mm-preview/news']


def git(*args,cwd=None,**kwargs):
    return subprocess.check_output(['git',*args],cwd=cwd,**kwargs)


def subset(files,preview=False):
    return {p:h for p,h in files.items()if data_path(p)or preview and p.startswith(PREFIX)}


def inspect_tar(path):
    files={}
    with tarfile.open(path)as tar:
        for member in tar:
            if member.isdir():continue
            name=PurePosixPath(member.name)
            if not member.isfile()or name.is_absolute()or '..'in name.parts or str(name)in files:
                raise ValueError('Unsafe public data archive')
            with tar.extractfile(member)as stream:files[str(name)]=hashlib.file_digest(stream,'sha256').hexdigest()
    return files


def recover(repo,commit,expected,folder,preview=False):
    roots=DATA_ROOTS+(['app/'+PREFIX.rstrip('/')]if preview else[])
    archive=folder/(commit+'.tar')
    with archive.open('wb')as stream:
        subprocess.run(['git','archive','--format=tar',commit,*roots],cwd=repo,stdout=stream,check=True)
    recovered={p.removeprefix('app/'):h for p,h in inspect_tar(archive).items()if p.removeprefix('app/')in expected}
    if recovered!=expected:raise ValueError('Public Git recovery differs from reviewed bytes')
    archive.unlink()


def preserve(site,candidate,receipt):
    review=read(REVIEW);new=read(candidate)
    validate_candidate(site,review,new)
    origin=git('remote','get-url','origin',text=True).strip()
    if origin.removesuffix('.git')!=URL.removesuffix('.git'):raise ValueError('Unexpected publication repository')
    subprocess.run(['gh','auth','setup-git','--hostname','github.com'],check=True)
    git('fetch','--no-tags','origin',MIRROR)
    parent=git('rev-parse','FETCH_HEAD',text=True).strip()
    old_expected=subset(review['files']);new_expected=subset(new['files'],preview=True)
    index=json.loads(git('show',parent+':app/mm-preview/current/index.json'))
    if index['forecast_sha256']!=new['data_refresh']['previous_forecast_sha256']:
        raise ValueError('Publication mirror advanced; review before writing data')
    with tempfile.TemporaryDirectory()as folder:
        folder=Path(folder)
        # Recover the old original data before any write. Commit history is permanent.
        recover(Path.cwd(),parent,old_expected,folder)
        env=dict(os.environ,GIT_INDEX_FILE=str(folder/'index'))
        subprocess.run(['git','read-tree',parent],env=env,check=True)
        entries=[]
        for name in sorted(new_expected):
            if '\n'in name or '\t'in name:raise ValueError('Unsafe public path')
            oid=git('hash-object','-w',str((site/name).resolve()),text=True).strip()
            entries.append('100644 '+oid+'\tapp/'+name+'\n')
        subprocess.run(['git','update-index','--index-info'],env=env,input=''.join(entries),text=True,check=True)
        tree=git('write-tree',env=env,text=True).strip()
        commit=git('-c','user.name=FPL public data publisher','-c','user.email=mm-preview@users.noreply.github.com','commit-tree',tree,'-p',parent,input='Refresh verified original public data and retain isolated preview [skip ci]\n',text=True).strip()
        changed=git('diff-tree','--no-commit-id','--name-only','-r','-z',parent,commit).decode().split('\0')
        if any(p and p.removeprefix('app/')not in new_expected for p in changed):raise ValueError('Unapproved mirror path changed')
        recover(Path.cwd(),commit,new_expected,folder,preview=True)
        # Normal existing publisher mechanism: a fast-forward, never force/replace.
        subprocess.run(['git','push','origin',commit+':refs/heads/'+MIRROR],check=True)
        remote=git('ls-remote','origin','refs/heads/'+MIRROR,text=True).split()[0]
        if remote!=commit:raise ValueError('Publication mirror advanced during verification')
        # A fresh repository proves recovery without the current workspace/object cache.
        recovered=folder/'fresh';recovered.mkdir()
        git('init','--quiet',cwd=recovered);git('remote','add','origin',URL,cwd=recovered)
        git('config','remote.origin.promisor','true',cwd=recovered)
        git('config','remote.origin.partialclonefilter','blob:none',cwd=recovered)
        git('fetch','--quiet','--no-tags','--depth=1','--filter=blob:none','origin',parent,commit,cwd=recovered)
        recover(recovered,parent,old_expected,folder)
        recover(recovered,commit,new_expected,folder,preview=True)
    result=dict(schema='fpl-existing-public-mirror-recovery-v1',repository=REPO,branch=MIRROR,previous_commit=parent,commit=commit,previous_files_sha256=hashlib.sha256(canonical(old_expected)).hexdigest(),files_sha256=hashlib.sha256(canonical(new_expected)).hexdigest(),old_files_recovered=len(old_expected),new_files_recovered=len(new_expected),recovered_without_workspace=True)
    receipt.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True))


def verify_receipt(site,review,candidate,receipt,get):
    r=read(receipt);old=subset(review['files']);new=subset(candidate['files'],preview=True)
    if (r.get('schema')!='fpl-existing-public-mirror-recovery-v1'or r.get('repository')!=REPO or r.get('branch')!=MIRROR or
        r.get('previous_files_sha256')!=hashlib.sha256(canonical(old)).hexdigest()or r.get('files_sha256')!=hashlib.sha256(canonical(new)).hexdigest()or r.get('recovered_without_workspace')is not True or
        not re.fullmatch('[a-f0-9]{40}',r.get('commit',''))or not re.fullmatch('[a-f0-9]{40}',r.get('previous_commit',''))):
        raise ValueError('Permanent public mirror recovery receipt differs')
    commit=get(f'repos/{REPO}/git/commits/{r["commit"]}')
    if r['previous_commit']not in [p['sha']for p in commit['parents']]:raise ValueError('Original public data is not retained in mirror ancestry')
    return r


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--site',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();preserve(a.site,a.candidate,a.receipt)
