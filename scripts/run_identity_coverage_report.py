#!/usr/bin/env python3
from pathlib import Path
import sys,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import run_horizon_policy_comparison as hp
from fpl_xpts.identity import resolve_uuid_to_fpl_ids
F=ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz'
f=pd.read_csv(F,usecols=['player_uuid','player']).drop_duplicates()
raw=hp.unpack_runtime('players_raw.csv').drop_duplicates('id').copy()
mapping,detail=resolve_uuid_to_fpl_ids(f,raw)
d=pd.DataFrame([x.__dict__ for x in detail])
names=f.set_index('player_uuid').player.astype(str).to_dict()
d['player']=d.player_uuid.map(names)
print('TOTAL',len(f))
print('MAPPED',len(mapping))
print('COVERAGE',len(mapping)/len(f))
print('METHODS',d.method.value_counts().to_dict())
print('UNRESOLVED',int(d.fpl_id.isna().sum()))
for r in d[d.fpl_id.isna()].sort_values(['score','player'],ascending=[False,True]).itertuples():
    print('MISS',repr(r.player),round(float(r.score),3),round(float(r.margin),3))
