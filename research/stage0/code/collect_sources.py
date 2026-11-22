"""Rebuild the public path/blob index from pinned refs (no network, no models).
The checked-in source-refs.json is a dated GitHub API observation, not a live list.
"""
import argparse,gzip,json,re,subprocess
from pathlib import Path
S=Path(__file__).resolve().parents[1]
def collect(repo,refs):
 entries={}
 for b in refs['branches']:
  if re.search(r'(manager|entry)[-_]\d{4,}',b['name'],re.I):raise ValueError('Private-manager ref in public manifest')
  tree=subprocess.check_output(['git','-C',str(repo),'ls-tree','-r',b['sha'],'--','analysis','docs','research','tests'],text=True)
  for line in tree.splitlines():
   _,typ,tail=line.split(None,2);blob,path=tail.split('\t',1)
   keep=path.startswith(('analysis/results/','docs/','research/','tests/')) or (path.startswith('analysis/') and ('test_' in path or 'verify_' in path))
   if typ!='blob' or not keep:continue
   if re.search(r'(manager|entry)[-_]\d{4,}',path,re.I)or'/private/'in path:continue
   entries.setdefault((path,blob),set()).add(b['sha'])
 return [dict(path=p,git_blob=b,commits=sorted(commits)) for (p,b),commits in sorted(entries.items())]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-git',required=True,type=Path);p.add_argument('--output',type=Path);a=p.parse_args();rows=collect(a.source_git,json.loads((S/'source-refs.json').read_text()))
 if a.output:a.output.write_bytes(gzip.compress(json.dumps(rows,separators=(',',':')).encode(),mtime=0))
 else:assert rows==json.loads(gzip.decompress((S/'tree-index.json.gz').read_bytes()))
 print(json.dumps({'distinct_path_blob_versions':len(rows),'mode':'write'if a.output else'checked against recorded index','model_execution':False}))
if __name__=='__main__':main()
