#!/usr/bin/env python3
"""Show exact remaining 2026/27 frozen vFinal adapter gaps, by verified file.

Read-only: never synthesize conditional-minute, penalty, bonus, or assistance
evidence and never mark a diagnostic source as live-certified.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
WORK=ROOT/'work/live-final-model'
SOURCES={
 'mm':WORK/'mm_frozen_diagnostic_six_gw.csv.gz',
 'player_events':BASE/'vfinal_player_event_components_6gw.csv.gz',
 'team_goals':BASE/'future_team_goal_lambdas.csv.gz',
 'keeper_saves':BASE/'keeper_lambda_saves_by_fixture_team.csv.gz',
 'penalty':BASE/'vfinal_live_penalty_inputs.csv.gz',
 'bps':BASE/'vfinal_live_bps_components.csv.gz'}
FIELDS={
 'mm':['fixture_uuid','player_uuid','team_id','target_gw','cutoff','pos',
       'p_start','xmins','mm_q_sub','mm_sub_minutes','start_minutes_mean'],
 'player_events':['fixture_uuid','player_uuid','goal_rate90','assist_rate90',
                  'dc_alpha','p_yellow','p_red','mu_dc'],
 'team_goals':['fpl_fixture_id','home_team_id','away_team_id','lambda_home_goals','lambda_away_goals'],
 'keeper_saves':['fixture_uuid','team_id','lambda_saves'],
 'penalty':['fixture_uuid','player_uuid','lambda_pen','pen_weight','pen_conversion','team_pen_conversion'],
 'bps':['fixture_uuid','player_uuid','bg_mean_rate90','bg_sd90']}
SPECIAL=['assist_probability_per_goal','start_minutes_mean']
def inspect(sources=SOURCES):
    results={};blockers=[]
    for name,path in sources.items():
        path=Path(path)
        if not path.is_file():
            results[name]={'status':'ABSENT','path':str(path)}
            blockers.append(name+': file absent')
            continue
        try:
            df=pd.read_csv(path,low_memory=False)
            missing=sorted(set(FIELDS[name])-set(df))
            bad=[c for c in FIELDS[name] if c in df and df[c].isna().any()]
            results[name]={'status':'INCOMPLETE' if missing or bad or df.empty else 'PRESENT_SCHEMA',
                           'rows':int(len(df)),'columns':len(df.columns),
                           'missing':missing,'null_fields':bad}
            if missing or bad or df.empty:blockers.append(name+': missing/null evidence: '+','.join(missing+bad))
        except Exception as exc:
            results[name]={'status':'INVALID','error_type':type(exc).__name__}
            blockers.append(name+': unreadable')
    # Other immutable vFinal inputs may be stored in one of the base CSVs,
    # but must not be synthesized from guessed mean rates.
    base_names=['mm','player_events','team_goals','keeper_saves']
    if all(Path(sources[x]).is_file() for x in base_names):
        cols=set()
        for name in base_names:
            try:cols.update(pd.read_csv(sources[name],nrows=0).columns)
            except Exception:pass
        for field in SPECIAL:
            if field not in cols:blockers.append('missing frozen prerequisite: '+field)
    return {'classification':'FROZEN_VFINAL_COMPONENT_PREFLIGHT_NOT_XP',
            'sources':results,'blockers':blockers,'ready':not blockers,
            'model_math_modified':False,'live_certified':False}
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,default=WORK/'frozen_vfinal_component_preflight.json')
    a=p.parse_args()
    result=inspect()
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    # Deliberately informational: strict source gate elsewhere fails if absent.
if __name__=='__main__':main()
