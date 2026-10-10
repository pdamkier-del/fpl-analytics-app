"""Restore checksum-verified 2026/27 source checkpoint; never overwrite a file.
This is a source/data checkpoint, not a certified live model release.
"""
import argparse,hashlib,io,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def restore(destination,checkpoint=None):
    base=Path(checkpoint) if checkpoint else ROOT/'model/checkpoints/live_inputs_20261010_v1'
    manifest=json.loads((base/'PARTS_MANIFEST.json').read_text())
    chunks=[]
    for row in manifest['parts']:
        p=(base/row['path']).resolve()
        if not p.is_relative_to(base.resolve()):raise ValueError('Invalid part path')
        b=p.read_bytes()
        if len(b)!=row['bytes'] or hashlib.sha256(b).hexdigest()!=row['sha256']:raise ValueError('Part digest mismatch')
        chunks.append(b)
    archive=b''.join(chunks)
    if hashlib.sha256(archive).hexdigest()!=manifest['archive_sha256']:raise ValueError('Archive digest mismatch')
    dest=Path(destination).resolve();expected={r['path']:r for r in manifest['files']};writes=[]
    with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as t:
        if {m.name for m in t.getmembers()}!=set(expected):raise ValueError('Archive membership mismatch')
        for m in t.getmembers():
            p=(dest/m.name).resolve()
            if not p.is_relative_to(dest) or not m.isfile():raise ValueError('Invalid archive member')
            b=t.extractfile(m).read();r=expected[m.name]
            if len(b)!=r['bytes'] or hashlib.sha256(b).hexdigest()!=r['sha256']:raise ValueError('File digest mismatch')
            if p.exists() and p.read_bytes()!=b:raise FileExistsError('Refusing to replace: '+str(p))
            writes.append((p,b))
    for p,b in writes:
        if not p.exists():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    return {'files':len(writes),'archive_sha256':manifest['archive_sha256'],'live_model_certified':False}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);a=ap.parse_args();print(json.dumps(restore(a.out)))
