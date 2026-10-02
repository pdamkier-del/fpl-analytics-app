#!/usr/bin/env python3
"""Restore the unchanged frozen Core from lossless, checksum-verified Git parts."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def restore(out):
    root=ROOT/'model/checkpoints/phase5e_core'
    manifest=json.loads((root/'PARTS_MANIFEST.json').read_text())
    out=Path(out).resolve()
    if out.exists():
        if digest(out)==manifest['sqlite_sha256']:return 'already verified'
        raise FileExistsError('Refusing to overwrite a different existing database: '+str(out))
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fpl-core-restore-',dir=out.parent) as scratch:
        compressed=Path(scratch)/'core.gz';database=Path(scratch)/'core.sqlite3'
        with open(compressed,'wb') as dest:
            for entry in manifest['parts']:
                source=(root/entry['path']).resolve()
                if not source.is_relative_to(root.resolve()):raise ValueError('Invalid part path')
                if source.stat().st_size!=entry['bytes'] or digest(source)!=entry['sha256']:raise ValueError('Part checksum mismatch: '+entry['path'])
                with open(source,'rb') as part:shutil.copyfileobj(part,dest)
        if digest(compressed)!=manifest['compressed_sha256']:raise ValueError('Compressed Core checksum mismatch')
        with gzip.open(compressed,'rb') as source,open(database,'wb') as dest:shutil.copyfileobj(source,dest)
        if digest(database)!=manifest['sqlite_sha256']:raise ValueError('SQLite checksum mismatch')
        os.replace(database,out)
    return 'restored and verified'


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',default=str(ROOT/'work/core.sqlite3'))
    args=ap.parse_args();print(restore(args.out))
