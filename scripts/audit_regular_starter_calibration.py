#!/usr/bin/env python3
"""Prefix-only diagnostic of regular starters; never forces P(start)=100%."""
from pathlib import Path
import sys,json,sqlite3,hashlib
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'analysis/results/full-model-audit-20261012'
def cohort(m):
 m=m.copy();m['at']=pd.to_datetime(m.cutoff,utc=True);m['known']=pd.to_datetime(m.outcome_known_at,utc=True);rows=[];already_known=0
 for _,g in m.groupby('player_uuid'):
  g=g.sort_values('known');known=g.known.astype('int64').to_numpy();at=g['at'].astype('int64').to_numpy();y=g.y.to_numpy()
  for i,r in enumerate(g.itertuples()):
   if known[i]<=at[i]:already_known+=1;continue
   n=int(np.searchsorted(known,at[i],side='left'))
   if n>=6 and (y[n-6:n]==1).all():rows.append(dict(gw=int(r.gw),pos=r.pos,p_start=float(r.new_p_start),started=int(r.y),xmins=float(r.new_xmins),minutes=float(r.minutes)))
 return pd.DataFrame(rows),already_known

def summarize(f):return dict(rows=len(f),predicted_start=float(f.p_start.mean()),actual_start=float(f.started.mean()),predicted_minutes=float(f.xmins.mean()),actual_minutes=float(f.minutes.mean()))
def main():
 m=pd.read_csv(OUT/'locked-2125/locked-mm-final-gw6-38/locked_mm_predictions.csv.gz');f,already=cohort(m)
 manifest=json.loads((ROOT/'model/checkpoints/phase5e_core/PARTS_MANIFEST.json').read_text());core=ROOT/'work/core.sqlite3'
 if hashlib.sha256(core.read_bytes()).hexdigest()!=manifest['sqlite_sha256']:raise ValueError('Frozen Core checksum mismatch')
 with sqlite3.connect(core.resolve().as_uri()+'?mode=ro',uri=True) as c:
  inventory=pd.read_sql_query('select season,count(*) as player_fixture_rows,min(observed_at) as earliest_capture,max(observed_at) as latest_capture from player_fixture_observations group by season',c).to_dict('records')
 report=dict(classification='REUSED_LOCKED_MM_REGULAR_STARTER_CALIBRATION',definition='At least six observed prior appearances, last six started; outcomes strictly before target cutoff',summary=summarize(f),by_position={pos:summarize(g) for pos,g in f.groupby('pos')},targets_already_known_excluded=already,core_sha256=manifest['sqlite_sha256'],core_inventory=inventory,availability_note='Archived role/MM outcome clock uses kickoff+3h; current live source and new duration experiments use kickoff+4h. Neither establishes actual publication availability.',promotion_allowed=False,limitations=['Archived GW6-38 predictions are reused diagnostic data, not an independent holdout','2022-23 and 2023-24 Core observations exist, but verified official deadline and historical future-snapshot bundles are absent from this audit checkout','No forced P(start)=1 and no player-specific patch'])
 (OUT/'regular_starter_calibration_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
