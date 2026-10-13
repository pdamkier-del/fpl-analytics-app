#!/usr/bin/env python3
"""Capture unchanged original-PM inputs for a serial offline A/B test.

2025 uses archived original point results while capturing the exact warm-history
input recipe already verified against all 26,159 frozen outputs. No guessed
results are emitted. 2024 limits the existing conditional adapter to current-GW
fixtures; this is an evaluation scope, not a change to fitted model equations.
"""
import argparse,inspect,sys,json,gzip,runpy
from pathlib import Path
from dataclasses import asdict
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.joint_simulator import simulate_many
from audit_capture_io import write_records

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--season',choices=['2024-25','2025-26'],required=True);ap.add_argument('--source-root',required=True);ap.add_argument('--archive');ap.add_argument('--out',required=True);ap.add_argument('--start-origin',type=int,default=6);ap.add_argument('--end-origin',type=int,default=38);a=ap.parse_args()
 source=Path(a.source_root).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
 records=[]
 if a.season=='2025-26' and (a.start_origin,a.end_origin)!=(6,38):raise ValueError('2025 archived seed counters require the full original range')
 if a.season=='2025-26':
  archive=Path(a.archive).resolve();frozen=pd.read_csv(archive/'rolling-vfinal-final-gw6-38/fixture_predictions.csv.gz')
  lookup={(int(r.decision_gw),str(r.fixture),str(r.player_uuid)):float(r.xpts_fixture) for r in frozen.itertuples()}
  path=source/'scripts/run_rolling_vfinal_gw6_38.py';namespace=runpy.run_path(str(path),run_name='capture_original')
  argv=[str(path),'--db',str(source/'work/core.sqlite3'),'--source',str(source/'analysis/results/workload-final-gw1/all_features.csv.gz'),'--mm',str(archive/'locked-mm-final-gw6-38/locked_mm_predictions.csv.gz'),'--out',str(out/'captured_reference')]
 else:
  path=source/'scripts/run_2024_25_conditional_pm.py';text=path.read_text();needle="fx=sched[sched.gameweek.between(origin,min(38,origin+5)) & (sched.kickoff>=cutoff)]"
  if text.count(needle)!=1:raise ValueError('Conditional adapter scope changed')
  text=text.replace(needle,"fx=sched[sched.gameweek.eq(origin) & (sched.kickoff>=cutoff)]")
  namespace={'__file__':str(path),'__name__':'capture_conditional'};exec(compile(text,str(path),'exec'),namespace)
  argv=[str(path),'--db',str(source/'work/core.sqlite3'),'--derived',str(source/'data_v1_1/derived/season_2024_25_v1'),'--source',str(source/'analysis/results/conditional-2024-25-mm/conditional_feature_frame.csv.gz'),'--mm',str(source/'analysis/results/conditional-2024-25-mm/locked_mm_predictions.csv.gz'),'--out',str(out/'captured_reference')]
 def capture(inp,n,seed):
  caller=inspect.currentframe().f_back.f_locals;fr=caller['fr'];origin=int(caller['origin'])
  if int(fr.gameweek)!=origin:raise ValueError('Capture requires current-GW fixtures')
  metadata=dict(origin=origin,fixture=str(fr.match_id),seed=int(seed),input=asdict(inp),home=int(fr.home_team_id),away=int(fr.away_team_id),players=[dict(player_uuid=str(r.player_uuid),pos=str(r.pos),player=str(r.player)) for r in caller['rg'].itertuples()])
  if a.season=='2025-26':
   scores={p.player_id:{'xPts':lookup[(origin,str(fr.match_id),p.player_id)]} for p in inp.players if (origin,str(fr.match_id),p.player_id) in lookup}
   if not records:
    check=simulate_many(inp,n=n,seed=seed)
    if any(check[pid]['xPts']!=r['xPts'] for pid,r in scores.items()):raise ValueError('Original warm-input smoke no longer exact')
  else:scores=simulate_many(inp,n=n,seed=seed)
  metadata['reference']={pid:s['xPts'] for pid,s in scores.items()};records.append(metadata)
  return scores
 namespace['main'].__globals__['simulate_many']=capture
 argv.extend(['--start-origin',str(a.start_origin),'--end-origin',str(a.end_origin)])
 previous=sys.argv
 try:sys.argv=argv;namespace['main']()
 finally:sys.argv=previous
 write_records(out/'inputs.jsonl.gz',records)
 print('Captured',a.season,len(records),'fixtures',flush=True)
if __name__=='__main__':main()
