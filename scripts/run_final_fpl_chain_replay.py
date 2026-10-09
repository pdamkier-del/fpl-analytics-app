#!/usr/bin/env python3
"""Assembled frozen MM→PM→TS→FH/WC/BB/TC historical replay.

vFinal inputs and TC scenario artifacts are historical external archives.
No locked model is recalibrated; scores use official existing point-scoring.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import run_joint_fh_wc_stopping_replay as replay
from fpl_xpts.simple_chip_thresholds import LOCKED_LAMBDA_FH,LOCKED_LAMBDA_WC
from fpl_xpts.bench_boost_policy import LOCKED_LAMBDA_BB
from fpl_xpts.tc_chip_bridge import tc_origin_provider

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--vfinal',required=True)
    p.add_argument('--tc-origins',required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names,forecast=replay.load(a.vfinal)
    without_tc=replay.run(
        'frozen_fh_wc_bb',gws,names,forecast,use_chips=True,
        simple_thresholds=(LOCKED_LAMBDA_FH,LOCKED_LAMBDA_WC),
        bb_lambda=LOCKED_LAMBDA_BB)
    if without_tc['total_points']!=2242:
        raise AssertionError('Previously verified FH/WC/BB baseline changed')
    without_tc_frame=pd.DataFrame(without_tc.pop('logs'))
    without_tc_frame.to_csv(out/'frozen_without_tc_gameweeks.csv',index=False)
    full=replay.run(
        'assembled_all_chips',gws,names,forecast,use_chips=True,
        simple_thresholds=(LOCKED_LAMBDA_FH,LOCKED_LAMBDA_WC),
        bb_lambda=LOCKED_LAMBDA_BB,
        tc_provider=tc_origin_provider(a.tc_origins))
    rows=pd.DataFrame(full.pop('logs'))
    rows.to_csv(out/'all_chips_gameweeks.csv',index=False)
    for start,end in ((1,19),(20,38)):
        part=rows[rows.gw.between(start,end)]
        for chip in ('wc','fh','bb','tc'):
            if int(part.chip.eq(chip).sum())>1:
                raise AssertionError(f'Multiple {chip} uses in {start}-{end}')
        if len(part)!=end-start+1:
            raise AssertionError('Missing GW')
    if full['total_points']!=int(rows.score.sum()):
        raise AssertionError('Replay point total mismatch')
    chips=rows[rows.chip.ne('normal')][
        ['gw','chip','score','bb_gain','bb_realized_uplift','tc_candidate_id','tc_q','tc_action','hit_cost']
    ]
    chips.to_csv(out/'chip_decisions.csv',index=False)
    summary={
        'classification':'assembled historical replay; not cutoff-certified prospective TC',
        'source_period':'2025-26 GW1-38',
        'locked':{'FH':LOCKED_LAMBDA_FH,'WC':LOCKED_LAMBDA_WC,'BB':LOCKED_LAMBDA_BB,'TC':'existing TC-v2 defaults'},
        'fh_wc_bb_baseline_points':int(without_tc['total_points']),
        'assembled':full,
        'chip_decisions':chips.to_dict('records'),
        'delta_from_fh_wc_bb':int(full['total_points']-without_tc['total_points']),
        'note':'Archived TC future schedule may use realized calendar and is not independently cutoff-certified; current TC candidates restricted to the TS starting XI. TC may alter captain assignment but not XI or transfers.',
    }
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print('FINAL_ASSEMBLED_FPL',json.dumps(summary),flush=True)

if __name__=='__main__':main()
