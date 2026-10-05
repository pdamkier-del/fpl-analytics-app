#!/usr/bin/env python3
"""9-way transfer strategy grid: 3 horizon/weight policies x 3 hit buffers.

Chips OFF in every replay.

Policies:
- 3GW conservative: (1.00, 0.85, 0.70)
- 3GW stronger decay sensitivity: (1.00, 0.80, 0.60)
- 6GW decay: (1.00, 0.85, 0.70, 0.55, 0.40, 0.25)

Hit uncertainty buffers:
- 1.0
- 1.5
- 2.0

This uses the recovered rolling Phase5Q archive as a full-season strategy proxy
until cutoff-safe vFinal rolling origin->future forecasts are available.
It is NOT a vFinal season-performance result.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))

import run_horizon_policy_comparison as hp
from run_v4rc_experiment import write_json,sha

OUT=ROOT/'analysis/results/transfer-grid-9replays-20261005-v1'

POLICIES={
 '3gw_085_070':(1.00,.85,.70),
 '3gw_080_060':(1.00,.80,.60),
 '6gw_decay':(1.00,.85,.70,.55,.40,.25),
}
BUFFERS=[1.0,1.5,2.0]


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    OUT.mkdir(parents=True)

    gws=hp.unpack_runtime('merged_gw.csv')
    raw=hp.unpack_runtime('players_raw.csv')
    names=raw.set_index('id').web_name.astype(str).to_dict()
    forecast=hp.rolling_forecast()[['id','web_name','position','gw','origin_gw','xpts_mean','p_play','fixtures']].copy()
    forecast.id=forecast.id.astype(int)

    rows=[]
    for policy,weights in POLICIES.items():
        for buf in BUFFERS:
            hp.HIT_BUFFER=float(buf)
            label=f'{policy}_buffer_{buf:.1f}'
            print('Running',label,flush=True)
            r=hp.run_policy(label,weights,gws,forecast,names)
            logs=pd.DataFrame(r.pop('logs'))
            logs.to_csv(OUT/f'{label}_gameweek_log.csv',index=False)
            dev=logs[logs.gw.between(1,21)]
            late=logs[logs.gw.between(22,38)]
            rows.append(dict(
              label=label,policy=policy,weights=list(weights),hit_buffer=float(buf),
              total_points=int(r['total_points']),transfers=int(r['transfers']),
              hit_points=int(r['hit_points']),uplift=int(r['uplift']),
              points_gw1_21=int(dev.score.sum()),points_gw22_38=int(late.score.sum()),
              transfers_gw1_21=int(dev.transfers.sum()),transfers_gw22_38=int(late.transfers.sum()),
              hit_points_gw1_21=int(dev.hit_cost.sum()),hit_points_gw22_38=int(late.hit_cost.sum()),
              no_transfer_control=int(r['no_transfer_control'])
            ))

    table=pd.DataFrame(rows).sort_values(
        ['total_points','hit_points','transfers'],ascending=[False,True,True]).reset_index(drop=True)
    table.to_csv(OUT/'comparison.csv',index=False)
    best=table.iloc[0].to_dict()

    # Robustness summaries: average rank and worst-period score by policy/buffer.
    table['rank_total']=table.total_points.rank(method='min',ascending=False)
    by_policy=table.groupby('policy').agg(
        mean_total=('total_points','mean'),min_total=('total_points','min'),max_total=('total_points','max'),
        mean_hits=('hit_points','mean'),mean_transfers=('transfers','mean'),
        mean_rank=('rank_total','mean')).reset_index().sort_values('mean_total',ascending=False)
    by_buffer=table.groupby('hit_buffer').agg(
        mean_total=('total_points','mean'),min_total=('total_points','min'),max_total=('total_points','max'),
        mean_hits=('hit_points','mean'),mean_transfers=('transfers','mean'),
        mean_rank=('rank_total','mean')).reset_index().sort_values('mean_total',ascending=False)
    by_policy.to_csv(OUT/'summary_by_policy.csv',index=False)
    by_buffer.to_csv(OUT/'summary_by_buffer.csv',index=False)

    summary=dict(
      classification='9-way transfer strategy proxy; chips off',
      forecast_provider='recovered rolling Phase5Q archive',
      policies={k:list(v) for k,v in POLICIES.items()},
      hit_buffers=BUFFERS,
      saved_ft_value=hp.SAVED_FT_VALUE,
      chips='OFF',
      results=rows,
      best=best,
      caveat='Not a vFinal full-season performance result. This isolates transfer horizon/weight and hit-buffer choices before regenerating cutoff-safe vFinal rolling forecasts.'
    )
    write_json(OUT/'summary.json',summary)
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(
      sources=[
        dict(path='scripts/run_transfer_grid_9replays.py',sha256=sha(Path(__file__))),
        dict(path='scripts/run_horizon_policy_comparison.py',sha256=sha(ROOT/'scripts/run_horizon_policy_comparison.py'))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    main()
