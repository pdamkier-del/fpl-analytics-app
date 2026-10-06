#!/usr/bin/env python3
"""Audit readiness for a true PM(vFinal)+TS(v4) rolling season replay.

A valid combined replay requires, at every decision GW d, forecasts produced
using only information available at that deadline for targets d..d+5.

This audit deliberately rejects target-GW vFinal diagnostic predictions as
rolling inputs because they were built at the target deadline, not the earlier
decision deadline.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_horizon_policy_comparison as hp
from fpl_v1_1_model.paired_joint import read_frozen_table

ROLL=ROOT/'analysis/results/legacy-rolling-recovery-v1'
VFINAL=ROOT/'analysis/results/vfinal-integrated-20261005-v1'
OUT=ROOT/'analysis/results/pm-ts-combined-readiness-20261006-v1'


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    OUT.mkdir(parents=True)

    legacy=hp.rolling_forecast()
    required={(d,t) for d in range(1,39) for t in range(d,min(38,d+5)+1)}
    legacy_cells=set(zip(legacy.decision_gw.astype(int),legacy.gw.astype(int)))

    pred=pd.read_csv(VFINAL/'predictions.csv.gz')
    # vFinal integrated diagnostic has target GW but no origin/decision GW.
    # It is valid as current-deadline evidence only, never as earlier-horizon input.
    own_gws=sorted(pred.gw.astype(int).unique())
    vfinal_current_cells={(gw,gw) for gw in own_gws}
    true_rolling_cells=set()  # no origin-target vFinal table exists yet

    rows=[]
    for d,t in sorted(required):
        rows.append({
            'decision_gw':d,'target_gw':t,
            'legacy_phase5q_available':(d,t) in legacy_cells,
            'vfinal_target_deadline_only_available':(t,t) in vfinal_current_cells,
            'vfinal_cutoff_safe_for_this_origin':(d,t) in true_rolling_cells,
            'usable_for_true_pm_ts_replay':(d,t) in true_rolling_cells,
        })
    mat=pd.DataFrame(rows)
    mat.to_csv(OUT/'origin_target_coverage.csv',index=False)

    report={
      'classification':'PM+TS combined replay readiness audit',
      'required_origin_target_cells':len(required),
      'legacy_phase5q_cells':len(required & legacy_cells),
      'vfinal_current_deadline_gws':own_gws,
      'vfinal_true_rolling_cells':0,
      'missing_true_vfinal_cells':len(required),
      'full_combined_replay_ready':False,
      'reason':(
        'The integrated vFinal artifact contains target-deadline GW22-38 diagnostics, '
        'not six-GW forecasts frozen at each earlier decision deadline. Reusing them '
        'inside TS v4 would leak intervening information.'
      ),
      'correct_next_step':(
        'Generate cutoff-safe vFinal origin-target forecasts for all 213 required '
        'decision/target cells, then feed that table unchanged into TS v4.'
      ),
      'do_not_do':[
        'Do not relabel target-deadline vFinal predictions as earlier rolling forecasts.',
        'Do not blend target-deadline vFinal with later-known state and call it a full PM+TS replay.',
        'Do not tune TS while regenerating PM forecasts.'
      ],
    }
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
