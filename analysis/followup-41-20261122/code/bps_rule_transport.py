"""Quantify the identifiable CBI-unit rule difference, not a learned BPS correction."""
from pathlib import Path
import json,gzip
import pandas as pd
R=Path(__file__).resolve().parents[1];A=R.parent/'audits/2026-11-22';rows=[]
for gw in [8,9,10]:
 f=json.loads(gzip.decompress((A/f'inputs/archive/gw{gw}-forecast.json.gz').read_bytes()));pos={p['id']:p['position']for p in f['players']}
 for p in json.loads(gzip.decompress((A/f'inputs/archive/gw{gw}-live.json.gz').read_bytes()))['elements']:
  if p['id']not in pos:continue
  s=p['stats'];cbi=s['clearances_blocks_interceptions'];rows.append({'gw':gw,'id':p['id'],'position':pos[p['id']],'minutes':s['minutes'],'cbi':cbi,'old_cbi_bps':cbi//2,'current_cbi_bps':cbi//3,'current_minus_old':cbi//3-cbi//2})
d=pd.DataFrame(rows);s=d.groupby('position').agg(rows=('id','count'),played=('minutes',lambda x:int((x>0).sum())),old_cbi_bps=('old_cbi_bps','sum'),current_cbi_bps=('current_cbi_bps','sum'),delta=('current_minus_old','sum'));s.to_csv(R/'results/bps-cbi-unit-transport.csv');(R/'results/bps-identification.json').write_text(json.dumps({'scope':'Counterfactual scoring units applied to actual CBI counts; not predicted BPS error, not full proxy retargeting','sum_current_minus_old_cbi_bps':int(d.current_minus_old.sum()),'rows':len(d),'known_missing':['Being-tackled/dispossessed exact Opta semantics','Ordinary big-chance saves','Archived per-draw background-BPS target and covariance'],'warning':'DEF current CBI scoring is lower than the legacy proxy. Blindly switching this unit alone could lower DEF bonus further; observed low GK bonus cannot be assigned uniquely to this rule difference. Retarget and recalibrate rather than add raw points.'},indent=2));print(s.to_string())
