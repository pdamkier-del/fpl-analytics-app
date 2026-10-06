"""Restore losslessly split research datasets; validate all bytes, never overwrite differences."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def restore(folder):
    manifest=json.loads((folder/'PARTS_MANIFEST.json').read_text())
    for entry in manifest['files']:
        pieces=[]
        for part in entry['parts']:
            raw=(folder/part['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=part['sha256'] or len(raw)!=part['bytes']:
                raise ValueError('Part checksum failed: '+part['path'])
            pieces.append(raw)
        raw=b''.join(pieces)
        if hashlib.sha256(raw).hexdigest()!=entry['sha256'] or len(raw)!=entry['bytes']:
            raise ValueError('File checksum failed: '+entry['path'])
        target=folder/entry['path']
        if target.exists() and target.read_bytes()!=raw:
            raise FileExistsError('Refusing to overwrite different dataset: '+str(target))
        if not target.exists(): target.write_bytes(raw)
    expected=json.loads((folder/'SHA256_MANIFEST.json').read_text())
    for name,digest in expected.items():
        if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Dataset checksum failed: '+name)
    print('Restored and verified',len(expected),'research files')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--folder',type=Path,default=ROOT/'data_v1_1/derived/team_news_audit/2025-26-v2')
    restore(p.parse_args().folder)
