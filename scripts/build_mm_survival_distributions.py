#!/usr/bin/env python3
"""Export selected survival hazards from strictly prior outcomes for PM shape A/B."""
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from audit_mm_components import load_obs
from audit_capture_io import write_records
from fpl_v1_1_model.experimental_mm_research import survival_prediction

def main():
    out=ROOT/'analysis/results/mm-research-20261014';sel=json.loads((out/'selection.json').read_text())
    if not sel['selected_duration'].startswith('survival_'):raise ValueError('Development did not select a survival candidate')
    _,half,tau=sel['selected_duration'].split('_');obs={s:load_obs(ROOT/'work/core.sqlite3',s,h) for s,h in [('2024-25',4),('2025-26',3)]}
    for season in obs:
        frame=pd.read_csv(out/f'{season}_features.csv.gz');pool=obs[season].copy() if season=='2024-25' else pd.concat([obs['2024-25'],obs[season]],ignore_index=True);pool=pool.rename(columns={'fpl_position':'pos'});pool['pos']=pool.pos.replace({'GKP':'GK'});rows=[]
        for gw,g in frame.groupby('gw'):
            cut=pd.to_datetime(g.cutoff,utc=True).min();prior=pool[pool.started.eq(1)&pool.known.lt(cut)]
            means,hazards=survival_prediction(g,obs[season],prior,half_days=float(half),strength=float(tau),return_hazards=True)
            for r,mean,h in zip(g.itertuples(),means,hazards):rows.append(dict(gw=int(gw),fixture_uuid=r.fixture_uuid,player_uuid=r.player_uuid,mean=float(mean),hazard=h))
        write_records(out/f'{season}_starter_hazards.jsonl.gz',rows);print('Exported cutoff-safe hazards',season,len(rows),flush=True)
if __name__=='__main__':main()
