"""Restore only MM members of PR4's verified capsule; never run PM/TS."""
import hashlib,io,json,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REF='6d875a65251fb62f691dc0386ea81aeb29d27c0f'
MEMBERS=['2024-25_candidates.npz','2025-26_candidates.npz','selection.json','report.json','source_manifest.json','data_audit.json']
def restore(out):
    def read(path):return subprocess.check_output(['git','show',REF+':'+path],cwd=ROOT)
    m=json.loads(read('checkpoints/individual_mm_20261015/manifest.json'));chunks=[]
    for item in m['parts']:
        b=read('checkpoints/individual_mm_20261015/'+item['path'])
        if len(b)!=item['bytes']or hashlib.sha256(b).hexdigest()!=item['sha256']:raise ValueError('Invalid source capsule part')
        chunks.append(b)
    b=b''.join(chunks)
    if hashlib.sha256(b).hexdigest()!=m['zip_sha256']:raise ValueError('Invalid capsule')
    out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(b))as z:
        for name in MEMBERS:
            raw=z.read(name)
            if hashlib.sha256(raw).hexdigest()!=m['files'][name]['sha256']:raise ValueError('Invalid MM member')
            p=out/name
            if p.exists()and p.read_bytes()!=raw:raise ValueError('Refusing different existing member')
            p.write_bytes(raw)
    (out/'capsule_manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print('Restored six verified MM-only source members',flush=True)
if __name__=='__main__':restore(ROOT/'work/mm-source')
