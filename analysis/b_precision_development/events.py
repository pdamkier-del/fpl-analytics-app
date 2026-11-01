"""Paired two-thousand-draw predictive gates, immutable research baseline."""
import argparse,copy,gzip,hashlib,json
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict
from pathlib import Path
import pandas as pd
from precision_audit.dataset import load
from precision_audit.runner import run
from test_separated_goal_head import decode
from b_precision_calibration import apply
from b_simulation_precision import fixture_offset
WORK=Path('/workspace/scratch/b-precision-development-20261101');OUT=Path('analysis/results/b-precision-development-20261101')
def task(args):
 r,policy,arm,n,rep=args;seed=93000000+fixture_offset(r['fixture_uuid'],r['season'])+rep*1000003
 key=hashlib.sha256(json.dumps([r['season'],r['fixture_uuid'],policy,arm,n,seed],sort_keys=True).encode()).hexdigest();path=WORK/'event-cache'/(key+'.json.gz');path.parent.mkdir(exist_ok=True)
 if path.exists():return json.loads(gzip.decompress(path.read_bytes()))
 record=copy.deepcopy(r);inp=decode(copy.deepcopy(r['input']));inp,dist=apply(inp,r['dist'],r['meta'],policy,arm);record['input']=asdict(inp);record['dist']=dist;rows,receipt,_=run(record,n,seed)
 for row in rows:
  a=r['actual'][row['player_uuid']];row.update(arm=arm,actual_points=a['total_points'],actual_minutes=a['minutes'],actual_assists=a.get('fpl_assists',0),actual_start=a['started'],medical_return=r['meta'][row['player_uuid']]['return_active']and r['meta'][row['player_uuid']]['return_kind']=='medical_selection')
 out=dict(rows=rows,receipt=receipt);path.write_bytes(gzip.compress(json.dumps(out).encode(),mtime=0));return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--arms',nargs='+',default=['baseline','assist']);p.add_argument('--draws',type=int,default=2000);p.add_argument('--limit',type=int);a=p.parse_args();records=load(WORK/'historical-inputs.json.gz');records=[r for r in records if r['season']=='2025-26'or r['gw']>=30]
 if a.limit:records=records[:a.limit]
 policy=json.loads((OUT/'candidate-policy.json').read_text());results=[]
 with ProcessPoolExecutor(max_workers=2)as pool:
  fs=[pool.submit(task,(r,policy,arm,a.draws,0))for r in records for arm in a.arms]
  for i,f in enumerate(as_completed(fs)):
   results.append(f.result())
   if i%20==0:print('Paired event gate',i+1,'/',len(fs),flush=True)
 name='-'.join(a.arms)+'-'+str(a.draws);pd.DataFrame([r for x in results for r in x['rows']]).to_csv(OUT/(name+'-predictions.csv.gz'),index=False,compression={'method':'gzip','mtime':0});(OUT/(name+'-receipts.json')).write_text(json.dumps([x['receipt']for x in results],indent=2)+'\n')
if __name__=='__main__':main()
