"""Restore only checksummed 2024/25 data, with explicit derived-only repairs."""
from pathlib import Path
import gzip, hashlib, io, json, tarfile
ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'checkpoints/season_2024_25_v1'
ALLOWED=('data_v1_1/raw/season_2024_25_v1/','data_v1_1/derived/season_2024_25_v1/','analysis/results/season-2024-25-data-audit-v1/')
def read_archive(meta):
 chunks=[]
 for p in meta['parts']:
  b=(PACK/p['name']).read_bytes()
  assert len(b)==p['bytes'] and hashlib.sha256(b).hexdigest()==p['sha256'],p['name'];chunks.append(b)
 b=b''.join(chunks);assert hashlib.sha256(b).hexdigest()==meta['sha256']
 result={}
 with tarfile.open(fileobj=io.BytesIO(b),mode='r:xz') as t:
  for m in t.getmembers():
   assert m.isfile() and m.name.startswith(ALLOWED) and '..' not in Path(m.name).parts and not Path(m.name).is_absolute(),m.name
   assert m.name not in result,m.name
   result[m.name]=t.extractfile(m).read()
 return result

def restore():
 manifest=json.loads((PACK/'manifest.json').read_text());base=read_archive(manifest);staged=dict(base);repairs=set()
 for overlay in manifest.get('overlays',[]):
  values=read_archive(overlay);assert set(values)==set(overlay['supersedes'])
  for name in values:
   assert name.startswith('data_v1_1/derived/season_2024_25_v1/') or name=='analysis/results/season-2024-25-data-audit-v1/prepared_manifest.json',name
   assert name in base,name
  staged.update(values);repairs.update(values)
 # Validate all prepared gzip trailers before writing anything.
 for name,b in staged.items():
  if name.startswith('data_v1_1/derived/') and name.endswith('.gz'):gzip.decompress(b)
 for name,b in staged.items():
  p=ROOT/name
  if p.exists():
   old=p.read_bytes()
   assert old==b or (name in repairs and old==base[name]),'Refusing to overwrite differing checkpoint file: '+name
 for name,b in staged.items():
  p=ROOT/name
  if not p.exists() or (name in repairs and p.read_bytes()==base[name] and base[name]!=b):
   p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 print('Verified and restored',len(staged),'2024/25 files; no other season touched.')
if __name__=='__main__':restore()
