"""Restore only immutable 2024/25 data from checksummed repository parts."""
from pathlib import Path
import hashlib, io, json, tarfile
ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'checkpoints/season_2024_25_v1'
ALLOWED=('data_v1_1/raw/season_2024_25_v1/','data_v1_1/derived/season_2024_25_v1/','analysis/results/season-2024-25-data-audit-v1/')
def restore():
 manifest=json.loads((PACK/'manifest.json').read_text());chunks=[]
 for p in manifest['parts']:
  b=(PACK/p['name']).read_bytes()
  assert len(b)==p['bytes'] and hashlib.sha256(b).hexdigest()==p['sha256'],p['name'];chunks.append(b)
 b=b''.join(chunks);assert hashlib.sha256(b).hexdigest()==manifest['sha256']
 with tarfile.open(fileobj=io.BytesIO(b),mode='r:xz') as t:
  staged=[]
  for m in t.getmembers():
   assert m.isfile() and m.name.startswith(ALLOWED) and '..' not in Path(m.name).parts and not Path(m.name).is_absolute(),m.name
   v=t.extractfile(m).read();p=ROOT/m.name
   if p.exists():assert p.read_bytes()==v,'Refusing to overwrite differing checkpoint file: '+m.name
   staged.append((p,v))
  for p,v in staged:
   if not p.exists():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(v)
 print('Verified and restored',len(staged),'2024/25 files; no other season touched.')
if __name__=='__main__':restore()
