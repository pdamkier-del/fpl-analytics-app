#!/usr/bin/env python3
"""Fit 3-GW transfer weights with a temporal split.

Uses the same chips-OFF replay mechanics and recovered rolling Phase5Q forecasts
as the prior horizon-policy comparison. This is a strategy-weight fit, not a
vFinal full-season score.

Two stages:
1) test hand-picked 3-GW weight vectors;
2) fit a one-parameter exponential family w=(1,r,r^2).

Selection uses GW1-21 replay points. GW22-38 is reported as a later temporal
check and is not used to choose r.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))

from run_horizon_policy_comparison import (
    unpack_runtime,rolling_forecast,run_policy
)
from run_v4rc_experiment import write_json,sha

OUT=ROOT/'analysis/results/three-gw-weight-fit-20261005-v1'

HAND={
 'mild_090_075':(1.00,.90,.75),
 'current_085_070':(1.00,.85,.70),
 'medium_080_060':(1.00,.80,.60),
 'strong_075_050':(1.00,.75,.50),
 'very_strong_070_040':(1.00,.70,.40),
}
RHO=[.55,.60,.65,.70,.75,.80,.85,.90,.95]


def summarize_run(label,kind,param,weights,result):
    logs=pd.DataFrame(result['logs'])
    dev=logs[logs.gw.between(1,21)]
    test=logs[logs.gw.between(22,38)]
    return dict(
      label=label,kind=kind,param=param,weights=list(weights),
      total_points=int(result['total_points']),
      points_gw1_21=int(dev.score.sum()),
      points_gw22_38=int(test.score.sum()),
      transfers=int(result['transfers']),
      hit_points=int(result['hit_points']),
      transfers_gw1_21=int(dev.transfers.sum()),
      transfers_gw22_38=int(test.transfers.sum()),
      hit_points_gw1_21=int(dev.hit_cost.sum()),
      hit_points_gw22_38=int(test.hit_cost.sum()),
    ),logs


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    gws=unpack_runtime('merged_gw.csv')
    raw=unpack_runtime('players_raw.csv')
    names=raw.set_index('id').web_name.astype(str).to_dict()
    forecast=rolling_forecast()[['id','web_name','position','gw','origin_gw','xpts_mean','p_play','fixtures']].copy()
    forecast.id=forecast.id.astype(int)

    rows=[]
    # hand-picked grid
    for label,w in HAND.items():
        print('Running',label,flush=True)
        r=run_policy(label,w,gws,forecast,names)
        row,logs=summarize_run(label,'hand','manual',w,r)
        rows.append(row)
        logs.to_csv(OUT/f'{label}_gameweek_log.csv',index=False)

    # exponential fit
    for rho in RHO:
        w=(1.0,float(rho),float(rho*rho))
        label=f'exp_rho_{rho:.2f}'
        print('Running',label,flush=True)
        r=run_policy(label,w,gws,forecast,names)
        row,logs=summarize_run(label,'exp',float(rho),w,r)
        rows.append(row)
        logs.to_csv(OUT/f'{label}_gameweek_log.csv',index=False)

    tab=pd.DataFrame(rows)
    tab.to_csv(OUT/'all_candidates.csv',index=False)

    hand=tab[tab.kind=='hand'].sort_values(
        ['points_gw1_21','hit_points_gw1_21','transfers_gw1_21'],
        ascending=[False,True,True]).reset_index(drop=True)
    exp=tab[tab.kind=='exp'].sort_values(
        ['points_gw1_21','hit_points_gw1_21','transfers_gw1_21'],
        ascending=[False,True,True]).reset_index(drop=True)
    hand.to_csv(OUT/'hand_grid_ranked.csv',index=False)
    exp.to_csv(OUT/'exp_fit_ranked.csv',index=False)

    best_hand=hand.iloc[0].to_dict()
    best_exp=exp.iloc[0].to_dict()
    # Primary selected fit: exponential family because it has one degree of freedom
    # and cleanly encodes increasing forecast uncertainty.
    selected=best_exp

    summary=dict(
      classification='3GW transfer-weight fit on recovered Phase5Q rolling forecasts; chips off',
      fit_family='w=(1,r,r^2)',
      rho_grid=RHO,
      hand_candidates={k:list(v) for k,v in HAND.items()},
      selection_period='GW1-21 only',
      later_temporal_check='GW22-38',
      selected=selected,
      best_hand=best_hand,
      all_results=rows,
      caveat='Strategy proxy only, not vFinal full-season performance. Same season is used for temporal fit/check, so final vFinal replay should still report sensitivity to nearby weights.'
    )
    write_json(OUT/'summary.json',summary)
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(
      sources=[
        dict(path='scripts/run_three_gw_weight_fit.py',sha256=sha(Path(__file__))),
        dict(path='scripts/run_horizon_policy_comparison.py',sha256=sha(ROOT/'scripts/run_horizon_policy_comparison.py'))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    main()
