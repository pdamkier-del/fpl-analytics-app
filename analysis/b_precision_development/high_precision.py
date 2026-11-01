"""Fixed four historical fixtures, two seeds, paired 10k-draw controls."""
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import pandas as pd
from precision_audit.dataset import load
from b_precision_development.events import task,WORK,OUT

def main():
 records=load(WORK/'historical-inputs.json.gz');policy=json.loads((OUT/'candidate-policy.json').read_text());chosen=[]
 for season,gws in [('2024-25',[32,36]),('2025-26',[24,32])]:
  for gw in gws:chosen.append(sorted([r for r in records if r['season']==season and r['gw']==gw],key=lambda r:r['fixture_uuid'])[0])
 results=[]
 with ProcessPoolExecutor(max_workers=2)as pool:
  fs=[pool.submit(task,(r,policy,arm,10000,rep))for r in chosen for arm in ['baseline','assist']for rep in [0,1]]
  for i,f in enumerate(as_completed(fs)):
   results.append(f.result());print('High precision paired control',i+1,'/',len(fs),flush=True)
 pd.DataFrame([r for x in results for r in x['rows']]).to_csv(OUT/'high-precision-controls.csv.gz',index=False,compression={'method':'gzip','mtime':0});(OUT/'high-precision-receipts.json').write_text(json.dumps([x['receipt']for x in results],indent=2)+'\n')
if __name__=='__main__':main()
