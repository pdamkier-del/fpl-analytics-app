#!/usr/bin/env python3
"""Per-GW MM player error audit for every player/team in the reused diagnostic.

Produces one row per player-fixture with:
team, player, modeled role, P(start), xMins, actual start, actual minutes,
start error, minute error, and error buckets.

This is an audit only. No MM/PM/TS parameters are changed.
"""
from __future__ import annotations
import sys,json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from run_mm_unified_official_roles import SOURCE,full_mm
from run_v4_performance_rating_experiment import build_perf_ledger,add_features as add_perf_features
from run_v4_three_state_sequence_experiment import add_sequence_features,write_gzip_csv
from run_mm_v2_xi_rating_experiment import add_xi_features

OUT=ROOT/'analysis/results/mm-gw-player-error-audit-20261006-v1'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    test=frame.gw.between(22,38).to_numpy()
    tcut=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
    train=(frame.gw.between(6,21)&(known<tcut)).to_numpy()

    p,q,sub,xmins,_=full_mm(frame.copy(),train)
    feat=add_xi_features(frame,p,0.0)

    cols=['fixture_uuid','gw','team_id','team','player_uuid','player','pos','expected_role','y','minutes']
    out=feat.loc[test,cols].copy()
    out['p_start']=p[test]
    out['xmins']=xmins[test]
    out['xi_selected_map']=feat.loc[test,'xi_selected_map'].to_numpy()
    out['xi_assigned_role']=feat.loc[test,'xi_assigned_role'].to_numpy()
    out['xi_formation']=feat.loc[test,'xi_formation'].to_numpy()
    out['actual_start']=out['y'].astype(float)
    out['start_abs_error']=(out['p_start']-out['actual_start']).abs()
    out['minute_error']=out['xmins']-out['minutes']
    out['minute_abs_error']=out['minute_error'].abs()

    def bucket(r):
        if r.p_start>=.8 and r.actual_start<.5:return 'HIGH_PSTART_DID_NOT_START'
        if r.p_start<=.2 and r.actual_start>=.5:return 'LOW_PSTART_STARTED'
        if r.xi_selected_map>=.5 and r.actual_start<.5:return 'MAP_XI_FALSE_POSITIVE'
        if r.xi_selected_map<.5 and r.actual_start>=.5:return 'MAP_XI_FALSE_NEGATIVE'
        if r.minute_abs_error>=45:return 'MINUTE_ERROR_45PLUS'
        if r.minute_abs_error>=30:return 'MINUTE_ERROR_30PLUS'
        return 'OK'
    out['error_bucket']=out.apply(bucket,axis=1)

    out=out.sort_values(['gw','team','player'])
    write_gzip_csv(out,OUT/'all_player_gw_predictions.csv.gz')

    # Worst rows overall.
    worst=out.sort_values(['minute_abs_error','start_abs_error'],ascending=False).head(500)
    worst.to_csv(OUT/'worst_player_gw_errors.csv',index=False)

    # Per-GW / team summaries.
    gw=out.groupby('gw',as_index=False).agg(
        n=('player_uuid','size'),
        start_mae=('start_abs_error','mean'),
        xmins_mae=('minute_abs_error','mean'),
        high_pstart_nonstart=('error_bucket',lambda s:(s=='HIGH_PSTART_DID_NOT_START').sum()),
        low_pstart_started=('error_bucket',lambda s:(s=='LOW_PSTART_STARTED').sum()),
        map_false_pos=('error_bucket',lambda s:(s=='MAP_XI_FALSE_POSITIVE').sum()),
        map_false_neg=('error_bucket',lambda s:(s=='MAP_XI_FALSE_NEGATIVE').sum()),
    )
    gw.to_csv(OUT/'by_gw.csv',index=False)

    team=out.groupby('team',as_index=False).agg(
        n=('player_uuid','size'),
        start_mae=('start_abs_error','mean'),
        xmins_mae=('minute_abs_error','mean'),
        high_pstart_nonstart=('error_bucket',lambda s:(s=='HIGH_PSTART_DID_NOT_START').sum()),
        low_pstart_started=('error_bucket',lambda s:(s=='LOW_PSTART_STARTED').sum()),
        map_false_pos=('error_bucket',lambda s:(s=='MAP_XI_FALSE_POSITIVE').sum()),
        map_false_neg=('error_bucket',lambda s:(s=='MAP_XI_FALSE_NEGATIVE').sum()),
    ).sort_values('xmins_mae',ascending=False)
    team.to_csv(OUT/'by_team.csv',index=False)

    player=out.groupby(['team','player_uuid','player','pos','expected_role'],as_index=False).agg(
        appearances=('fixture_uuid','size'),
        avg_p_start=('p_start','mean'),
        actual_start_rate=('actual_start','mean'),
        start_mae=('start_abs_error','mean'),
        avg_xmins=('xmins','mean'),
        avg_actual_minutes=('minutes','mean'),
        xmins_mae=('minute_abs_error','mean'),
        worst_minute_error=('minute_abs_error','max'),
        high_pstart_nonstart=('error_bucket',lambda s:(s=='HIGH_PSTART_DID_NOT_START').sum()),
        low_pstart_started=('error_bucket',lambda s:(s=='LOW_PSTART_STARTED').sum()),
    ).sort_values(['team','xmins_mae'],ascending=[True,False])
    player.to_csv(OUT/'by_player.csv',index=False)

    summary={
        'rows':int(len(out)),
        'gameweeks':sorted(map(int,out.gw.unique())),
        'teams':int(out.team.nunique()),
        'players':int(out.player_uuid.nunique()),
        'mean_xmins_mae':float(out.minute_abs_error.mean()),
        'high_pstart_nonstart':int((out.error_bucket=='HIGH_PSTART_DID_NOT_START').sum()),
        'low_pstart_started':int((out.error_bucket=='LOW_PSTART_STARTED').sum()),
        'map_false_positive':int((out.error_bucket=='MAP_XI_FALSE_POSITIVE').sum()),
        'map_false_negative':int((out.error_bucket=='MAP_XI_FALSE_NEGATIVE').sum()),
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
