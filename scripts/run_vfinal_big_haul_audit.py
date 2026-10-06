#!/usr/bin/env python3
from pathlib import Path
import sys,unicodedata,json
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as base

OUT=ROOT/'analysis/results/vfinal-big-haul-audit-20261006-v1'
VF=ROOT/'analysis/results/vfinal-integrated-20261005-v1/predictions.csv.gz'
FEAT=ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz'

def norm(x):
 s=unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().casefold()
 return ''.join(c for c in s if c.isalnum())

def uuid_map():
 f=pd.read_csv(FEAT,usecols=['player_uuid','player']).drop_duplicates()
 raw=hp.unpack_runtime('players_raw.csv').drop_duplicates('id')
 cand={}
 for r in raw.itertuples():
  vals=[getattr(r,'web_name',''),f"{getattr(r,'first_name','')} {getattr(r,'second_name','')}"]
  for v in vals:
   k=norm(v)
   if k:cand.setdefault(k,set()).add(int(r.id))
 out={}
 for r in f.itertuples():
  ids=cand.get(norm(r.player),set())
  if len(ids)==1:out[str(r.player_uuid)]=next(iter(ids))
 return out

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 gws,names,forecast=base.prepare()
 mp=uuid_map()
 vf=pd.read_csv(VF)
 vf['id']=vf.player_uuid.astype(str).map(mp)
 vf=vf[vf.id.notna()].copy();vf.id=vf.id.astype(int)
 pred=vf.groupby(['gw','id'],as_index=False).agg(predicted_xp=('vfinal_xpts','sum'))
 rows=[]
 for gw in range(22,39):
  meta=hp.gw_meta(gws,names,gw)[['id','web_name','position','team']].drop_duplicates('id')
  act=hp.actual_gw(gws,gw)[['id','points','minutes']].rename(columns={'points':'actual_points'})
  z=meta.merge(pred[pred.gw==gw][['id','predicted_xp']],on='id',how='left').merge(act,on='id',how='left')
  z[['predicted_xp','actual_points','minutes']]=z[['predicted_xp','actual_points','minutes']].fillna(0)
  z['gw']=gw;z['surprise']=z.actual_points-z.predicted_xp
  rows.append(z)
 allp=pd.concat(rows,ignore_index=True)
 big=allp[(allp.actual_points>=10)|(allp.surprise>=8)].copy()
 big=big.sort_values(['surprise','actual_points'],ascending=False)
 big.to_csv(OUT/'big_hauls.csv',index=False)
 s={
  'rule':'actual >=10 or actual-predicted >=8',
  'count':int(len(big)),
  'top':big.head(40)[['gw','web_name','position','predicted_xp','actual_points','minutes','surprise']].round({'predicted_xp':2,'surprise':2}).to_dict(orient='records')
 }
 (OUT/'summary.json').write_text(json.dumps(s,indent=2)+'\n')
 print(json.dumps(s,indent=2))

if __name__=='__main__':main()
