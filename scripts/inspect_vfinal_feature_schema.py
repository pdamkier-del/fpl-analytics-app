#!/usr/bin/env python3
from pathlib import Path
import pandas as pd, json
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz'
f=pd.read_csv(p,nrows=5)
full=pd.read_csv(p,usecols=lambda c:c in {'gw','fixture_uuid','team_id','player_uuid','cutoff','outcome_known_at'})
print(json.dumps({
 'columns':list(f.columns),
 'sample':f.head(2).to_dict(orient='records'),
 'rows':len(full),
 'gws':[int(full.gw.min()),int(full.gw.max())],
 'rows_by_gw':full.groupby('gw').size().astype(int).to_dict(),
},indent=2,default=str))
