#!/usr/bin/env python3
"""Restore checksummed immutable real simulator outputs for desktop publication."""
import argparse,base64,hashlib,io,json,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
CHECKPOINT=ROOT/'model/checkpoints/live_vfinal_20261010_v1'
def restore(folder=CHECKPOINT,out=ROOT):
    manifest=json.loads((folder/'manifest.json').read_text());payload=b''
    for part in manifest['parts']:
        raw=(folder/part['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=part['sha256']:raise ValueError('Checkpoint part checksum mismatch')
        payload+=base64.b64decode(raw,validate=True)
    if hashlib.sha256(payload).hexdigest()!=manifest['archive_sha256']:raise ValueError('Checkpoint archive checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        if set(z.namelist())!=set(manifest['files']):raise ValueError('Checkpoint manifest files mismatch')
        for name,expected in manifest['files'].items():
            rel=PurePosixPath(name)
            if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe checkpoint path')
            data=z.read(name)
            if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Checkpoint file checksum mismatch')
            path=out/name;path.parent.mkdir(parents=True,exist_ok=True)
            if path.is_file() and path.read_bytes()==data:continue
            path.write_bytes(data)
    print('Verified simulator checkpoint:',len(manifest['files']),'files')
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT);p.add_argument('--checkpoint',type=Path,default=CHECKPOINT);a=p.parse_args();restore(folder=a.checkpoint,out=a.out)
if __name__=='__main__':main()
