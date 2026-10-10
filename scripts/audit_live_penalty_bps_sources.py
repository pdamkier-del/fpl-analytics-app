#!/usr/bin/env python3
"""Inventory REAL 2026/27 sources for frozen penalty/BPS live adapters.

An absent or partial source never authorizes inferred model values. Outputs
a machine-readable blockers report for the existing readiness workflow.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
WORK=ROOT/'work/live-final-model'
REQUIRED={
 'verified_penalty_attempts.csv.gz':['player_uuid','gw','attempts','penalties_scored','available_at'],
 'verified_penalty_team_sides.csv.gz':['gw','team_code','opp_code','attempts','available_at'],
 'verified_penalty_team_ids.csv.gz':['team_code','team_id'],
 'verified_bps_action_ledger.csv.gz':['player_uuid','available_at','minutes_played','bg_rate90',
  'cross_rate90','cbi_rate90','recovery_rate90','tackle_rate90','keypass_rate90',
  'dribble_rate90','foulwon_rate90','sot_rate90','passbps_rate90','negative_rate90']}
def inspect(directory=BASE):
    report={'classification':'2026_27_SOURCE_COVERAGE_ONLY_NOT_XP','ready':True,'files':{},'blockers':[]}
    for name,columns in REQUIRED.items():
        path=directory/name
        if not path.is_file():
            report['files'][name]={'present':False}
            report['blockers'].append(f'{name}: source absent')
            report['ready']=False
            continue
        try:
            df=pd.read_csv(path)
            missing=sorted(set(columns)-set(df))
            nulls={c:int(df[c].isna().sum()) for c in columns if c in df and df[c].isna().any()}
            details={'present':True,'rows':int(len(df)),'missing_columns':missing,'null_counts':nulls}
            report['files'][name]=details
            if df.empty or missing or nulls:
                report['ready']=False
                report['blockers'].append(f'{name}: incomplete evidence')
        except Exception as exc:
            report['ready']=False
            report['files'][name]={'present':True,'invalid':type(exc).__name__}
            report['blockers'].append(f'{name}: unreadable data')
    report['locked_model_active']=False
    return report
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--base',type=Path,default=BASE)
    p.add_argument('--output',type=Path,default=WORK/'live_penalty_bps_source_coverage.json')
    a=p.parse_args()
    result=inspect(a.base)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    if not result['ready']:raise SystemExit(2)
if __name__=='__main__':main()
