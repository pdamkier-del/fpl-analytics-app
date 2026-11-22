"""Verify frozen audit inputs; never refresh sources during reproduction."""
from pathlib import Path
import json,gzip,hashlib
ROOT=Path(__file__).resolve().parents[1]
def verify(root,entries):
 root=Path(root).resolve()
 for entry in entries:
  path=(root/entry['path']).resolve()
  if not path.is_relative_to(root):raise ValueError('Path outside audit root')
  raw=path.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('Checksum mismatch: '+entry['path'])
  if 'decoded_sha256'in entry and hashlib.sha256(gzip.decompress(raw)).hexdigest()!=entry['decoded_sha256']:raise ValueError('Decoded checksum mismatch: '+entry['path'])
 return len(entries)
if __name__=='__main__':print('Verified frozen evidence files:',verify(ROOT,json.loads((ROOT/'input-integrity.json').read_text())))
