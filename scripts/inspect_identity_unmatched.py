#!/usr/bin/env python3
from pathlib import Path
import sys,unicodedata,difflib,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import run_horizon_policy_comparison as hp
F=ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz'

def norm(x):
 s=unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().casefold()
 return ''.join(c for c in s if c.isalnum())

f=pd.read_csv(F)
raw=hp.unpack_runtime('players_raw.csv').drop_duplicates('id').copy()
teams=hp.unpack_runtime('teams_raw.csv').drop_duplicates('id')
team_name=dict(zip(teams.id.astype(int),teams.name.astype(str)))
print('FEATURE_COLUMNS',list(f.columns))
print('RAW_COLUMNS',list(raw.columns))
feat=f[['player_uuid','player']].drop_duplicates()
cand={}
for r in raw.itertuples():
 vals=[getattr(r,'web_name',''),f"{getattr(r,'first_name','')} {getattr(r,'second_name','')}"]
 for v in vals:
  k=norm(v)
  if k:cand.setdefault(k,set()).add(int(r.id))
un=feat[~feat.player.map(lambda x: len(cand.get(norm(x),set()))==1)].copy()
print('UNMATCHED_COUNT',len(un),'TOTAL',len(feat))
rawnames=[]
for r in raw.itertuples():
 for v in [getattr(r,'web_name',''),f"{getattr(r,'first_name','')} {getattr(r,'second_name','')}"]:
  if str(v).strip() and str(v)!='nan': rawnames.append((norm(v),str(v),int(r.id),getattr(r,'team',None),getattr(r,'element_type',None)))
keys=[x[0] for x in rawnames]
for r in un.head(120).itertuples():
 k=norm(r.player); ms=difflib.get_close_matches(k,keys,n=5,cutoff=.45)
 seen=[]
 for m in ms:
  for x in rawnames:
   if x[0]==m and x[2] not in [z[2] for z in seen]:seen.append(x)
 frow=f[f.player_uuid.astype(str)==str(r.player_uuid)].iloc[0]
 print('UNMATCHED',r.player_uuid,repr(r.player),'FEATURE_TEAM',repr(frow.get('team',None)),'TEAM_ID',repr(frow.get('team_id',None)),'NEAREST',[(x[1],x[2],team_name.get(int(x[3]),x[3]),round(difflib.SequenceMatcher(None,k,x[0]).ratio(),3)) for x in seen[:5]])
