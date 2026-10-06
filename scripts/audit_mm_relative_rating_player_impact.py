#!/usr/bin/env python3
"""Compare locked MM vs selected bounded relative-rating MM player by player."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'analysis/results/mm-gw-player-error-audit-20261006-v1/all_player_gw_predictions.csv.gz'
REL=ROOT/'analysis/results/mm-v2-relative-rating-competition-20261006-v1/reused_diagnostic_predictions.csv.gz'
OUT=ROOT/'analysis/results/mm-relative-rating-player-impact-20261006-v1'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    b=pd.read_csv(BASE)
    r=pd.read_csv(REL)
    keys=['fixture_uuid','player_uuid']
    keep=['fixture_uuid','player_uuid','v2_p_start','v2_xmins','rating_recent','rating_long_mean',
          'rating_self_delta','rating_trend','rating_comp_rel_gap','rating_comp_self_shock',
          'rating_comp_trend','rating_comp_adjustment','rating_comp_valid_roles',
          'xi_assigned_role','xi_formation']
    r=r[[c for c in keep if c in r.columns]]
    x=b.merge(r,on=keys,how='inner',suffixes=('_base','_rel'),validate='one_to_one')
    x['base_abs_min_error']=(x.xmins-x.minutes).abs()
    x['rel_abs_min_error']=(x.v2_xmins-x.minutes).abs()
    x['delta_abs_min_error']=x.rel_abs_min_error-x.base_abs_min_error
    x['base_start_abs_error']=(x.p_start-x.actual_start).abs()
    x['rel_start_abs_error']=(x.v2_p_start-x.actual_start).abs()
    x['delta_start_abs_error']=x.rel_start_abs_error-x.base_start_abs_error
    x['pstart_shift']=x.v2_p_start-x.p_start
    x['xmins_shift']=x.v2_xmins-x.xmins
    x['helped']=x.delta_abs_min_error<-.01
    x['hurt']=x.delta_abs_min_error>.01

    x.to_csv(OUT/'all_player_gw_impact.csv',index=False)

    team=x.groupby('team',as_index=False).agg(
        n=('player_uuid','size'),
        base_mae=('base_abs_min_error','mean'),
        relative_rating_mae=('rel_abs_min_error','mean'),
        delta_mae=('delta_abs_min_error','mean'),
        base_start_mae=('base_start_abs_error','mean'),
        relative_start_mae=('rel_start_abs_error','mean'),
        delta_start_mae=('delta_start_abs_error','mean'),
        helped_rows=('helped','sum'),
        hurt_rows=('hurt','sum'),
        mean_abs_pstart_shift=('pstart_shift',lambda s:float(np.mean(np.abs(s)))),
        max_abs_pstart_shift=('pstart_shift',lambda s:float(np.max(np.abs(s)))),
    ).sort_values('delta_mae')
    team.to_csv(OUT/'by_team.csv',index=False)

    player=x.groupby(['team','player_uuid','player','pos','expected_role'],as_index=False).agg(
        rows=('fixture_uuid','size'),
        base_mae=('base_abs_min_error','mean'),
        relative_rating_mae=('rel_abs_min_error','mean'),
        delta_mae=('delta_abs_min_error','mean'),
        delta_start_mae=('delta_start_abs_error','mean'),
        avg_pstart_shift=('pstart_shift','mean'),
        max_abs_pstart_shift=('pstart_shift',lambda s:float(np.max(np.abs(s)))),
        helped_rows=('helped','sum'),
        hurt_rows=('hurt','sum'),
    ).sort_values('delta_mae')
    player.to_csv(OUT/'by_player.csv',index=False)

    # Focus on large lineup errors, where rating is supposed to help.
    shocks=x[((x.p_start>=.8)&(x.actual_start<.5))|((x.p_start<=.2)&(x.actual_start>=.5))].copy()
    shocks=shocks.sort_values('delta_abs_min_error')
    shocks.to_csv(OUT/'lineup_shocks.csv',index=False)

    chelsea=x[x.team.eq('chelsea')].copy().sort_values(['gw','player'])
    chelsea.to_csv(OUT/'chelsea_all.csv',index=False)
    chelsea_worst=chelsea.sort_values('base_abs_min_error',ascending=False).head(100)
    chelsea_worst.to_csv(OUT/'chelsea_worst.csv',index=False)

    summary={
        'rows':int(len(x)),
        'teams':int(x.team.nunique()),
        'players':int(x.player_uuid.nunique()),
        'base_mae':float(x.base_abs_min_error.mean()),
        'relative_rating_mae':float(x.rel_abs_min_error.mean()),
        'delta_mae':float(x.delta_abs_min_error.mean()),
        'base_start_mae':float(x.base_start_abs_error.mean()),
        'relative_start_mae':float(x.rel_start_abs_error.mean()),
        'lineup_shocks':int(len(shocks)),
        'shock_base_mae':float(shocks.base_abs_min_error.mean()),
        'shock_relative_rating_mae':float(shocks.rel_abs_min_error.mean()),
        'shock_delta_mae':float(shocks.delta_abs_min_error.mean()),
        'chelsea_base_mae':float(chelsea.base_abs_min_error.mean()),
        'chelsea_relative_rating_mae':float(chelsea.rel_abs_min_error.mean()),
        'chelsea_delta_mae':float(chelsea.delta_abs_min_error.mean()),
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
