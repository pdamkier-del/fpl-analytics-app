#!/usr/bin/env python3
"""Construct observed current-season team xG from completed FPL player matches.

Only sums source-reported xG for teams whose played-player xG coverage is
complete. Missing data is not zero and no model coefficients are changed.
Derived team inputs are source evidence, not vFinal model inference.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
OUT=BASE/'observed_team_xg_history.csv.gz'
AUDIT=ROOT/'work/live-final-model/live_team_xg_provenance.json'

def build():
    f=pd.read_csv(BASE/'player_fixture_observations.csv.gz',low_memory=False)
    needed={'fixture_uuid','team_id','opponent_team_id','was_home','gw',
        'kickoff_at','available_at','minutes','xg','player_uuid'}
    if missed:=needed-set(f):
        raise ValueError('Missing team xG source fields: '+str(sorted(missed)))
    if f.duplicated(['fixture_uuid','player_uuid']).any():
        raise ValueError('Duplicate player/match xG rows')
    played=f[pd.to_numeric(f.minutes,errors='coerce').gt(0)].copy()
    played['xg']=pd.to_numeric(played.xg,errors='coerce')
    quality=played.groupby(['fixture_uuid','team_id']).agg(
        active_players=('player_uuid','nunique'),players_with_xg=('xg','count'),
        xg=('xg','sum'),
        opponents=('opponent_team_id','nunique'),
        sides=('was_home','nunique'),
        gameweeks=('gw','nunique'))
    accepted=quality[(quality.active_players>=11)&
        (quality.active_players==quality.players_with_xg)&
        (quality.opponents==1)&(quality.gameweeks==1)].copy()
    bad=quality.index.difference(accepted.index)
    if accepted.empty:raise ValueError('No team-fixtures with full source FPL player xG coverage')
    rows=f.merge(accepted[['xg']],left_on=['fixture_uuid','team_id'],
        right_index=True,how='inner',suffixes=('','_team'))
    cols=['fixture_uuid','team_id','opponent_team_id','was_home','gw','kickoff_at','available_at','xg_team']
    result=rows[cols].drop_duplicates(['fixture_uuid','team_id'])
    result=result.rename(columns={'xg_team':'xg'})
    result['season']='2026-27'
    result['kickoff_at']=pd.to_datetime(result.kickoff_at,utc=True)
    result['available_at']=pd.to_datetime(result.available_at,utc=True)
    if (result.available_at<=result.kickoff_at).any():raise ValueError('Postmatch availability timing corrupt')
    if (~np.isfinite(result.xg.to_numpy(float))).any() or (result.xg<0).any():
        raise ValueError('Invalid actual team xG source')
    result.to_csv(OUT,index=False,compression='gzip')
    report={'classification':'OFFICIAL_FPL_OBSERVED_TEAM_XG_SOURCE_NOT_LIVE_PM',
            'season':'2026-27','played_player_rows':len(played),
            'team_fixture_sides_total':len(quality),'complete_sides':len(accepted),
            'incomplete_sides':len(bad),
            'team_fixture_sides_incomplete':[
                {'fixture_uuid':str(key[0]),'team_id':int(key[1]),
                 'players':int(quality.loc[key,'active_players']),
                 'with_xg':int(quality.loc[key,'players_with_xg'])}
                for key in list(bad)[:50]],
            'current_matches_with_two_complete_sides':int(result.groupby('fixture_uuid').team_id.nunique().eq(2).sum()),
            'vfinal_run_completed':False}
    AUDIT.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('OFFICIAL CURRENT TEAM XG:',json.dumps({k:v for k,v in report.items()
        if k not in ['team_fixture_sides_incomplete']},ensure_ascii=False))
    return result

if __name__=='__main__':build()
