"""Permanent recovery copy of an already-public/generated site via Releases.

Called only in the protected publisher, with a reviewed complete file manifest.
No manager data is collected. No overwrite flags and no private artifacts.
"""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
from refresh_data import REPO,digest,read


def inspect_tar(path):
    files={}
    with tarfile.open(path)as tar:
        for member in tar:
            if member.isdir():continue
            name=PurePosixPath(member.name)
            if not member.isfile()or name.is_absolute()or '..'in name.parts or str(name)in files:
                raise ValueError('Unsafe public Pages archive')
            with tar.extractfile(member)as stream:files[str(name)]=hashlib.file_digest(stream,'sha256').hexdigest()
    return files


def preserve(path,review,tag,target):
    expected=read(review)
    if inspect_tar(path)!=expected['files']:raise ValueError('Recovery archive differs from reviewed public bytes')
    with tempfile.TemporaryDirectory()as folder:
        folder=Path(folder);archive=folder/'original-pages.tar'
        try:archive.hardlink_to(path.resolve())
        except OSError:shutil.copy2(path,archive)
        shutil.copy2(review,folder/'baseline.json')
        note=folder/'notes.md';note.write_text('Original public forecast/site data preserved without a model rerun. Full file checksums and source provenance are in baseline.json. No private manager payloads. This data recovery record does not change research-protocol eligibility.\n')
        result=subprocess.run(['gh','release','view',tag,'--repo',REPO,'--json','assets'],capture_output=True)
        if result.returncode:
            subprocess.run(['gh','release','create',tag,str(archive),str(folder/'baseline.json'),'--repo',REPO,'--target',target,'--title','Preserved original public forecast data '+tag,'--notes-file',str(note),'--latest=false'],check=True)
        metadata=json.loads(subprocess.check_output(['gh','release','view',tag,'--repo',REPO,'--json','assets']))
        assets={a['name']:a for a in metadata['assets']}
        # Read provider digests from REST, since older gh versions omit them.
        release=json.loads(subprocess.check_output(['gh','api',f'repos/{REPO}/releases/tags/{tag}']))
        assets={a['name']:a for a in release['assets']}
        for name,source in [('original-pages.tar',archive),('baseline.json',review)]:
            if assets.get(name,{}).get('digest')!='sha256:'+digest(source):raise ValueError('Permanent recovery asset checksum mismatch')
        recovered=folder/'recovered';recovered.mkdir()
        subprocess.run(['gh','release','download',tag,'--repo',REPO,'--pattern','original-pages.tar','--dir',str(recovered)],check=True)
        if digest(recovered/'original-pages.tar')!=digest(path):raise ValueError('Permanent archive recovery failed')
    print(json.dumps(dict(tag=tag,recovery_verified=True,files=len(expected['files']),sha256=digest(path))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tar',type=Path,required=True);p.add_argument('--review',type=Path,required=True);p.add_argument('--tag',required=True);p.add_argument('--target',required=True);a=p.parse_args();preserve(a.tar,a.review,a.tag,a.target)
