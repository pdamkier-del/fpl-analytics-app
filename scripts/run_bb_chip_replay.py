#!/usr/bin/env python3
"""2025/26 joint FH/WC frozen strategy plus configurable Bench Boost."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import run_joint_fh_wc_stopping_replay as replay
from fpl_xpts.simple_chip_thresholds import LOCKED_LAMBDA_FH,LOCKED_LAMBDA_WC

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--vfinal',required=True)
    p.add_argument('--lambda-bb',type=float,required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names,forecast=replay.load(a.vfinal)
    result=replay.run('bb_lambda_'+str(a.lambda_bb),gws,names,forecast,
        use_chips=True,simple_thresholds=(LOCKED_LAMBDA_FH,LOCKED_LAMBDA_WC),
        bb_lambda=a.lambda_bb)
    gameweeks=pd.DataFrame(result.pop('logs'))
    gameweeks.to_csv(out/'gameweeks.csv',index=False)
    selected=gameweeks[gameweeks.chip.eq('bb')].copy()
    chip_weeks=gameweeks[gameweeks.chip.ne('normal')][['gw','chip','score','transfers','bb_gain','bb_q','bb_realized_uplift','bb_bench_names']]
    chip_weeks.to_csv(out/'selected_chips.csv',index=False)
    wc=result['wc_gws']
    result.update(lambda_bb=a.lambda_bb,lambda_fh=LOCKED_LAMBDA_FH,lambda_wc=LOCKED_LAMBDA_WC,
        delta_from_locked_fh_wc=result['total_points']-2209,
        bb_expected_incremental_xp=[float(x) for x in selected.bb_gain],
        bb_actual_incremental_points=[int(x) for x in selected.bb_realized_uplift],
        bb_benches=[dict(gw=int(x.gw),players=x.bb_bench_names) for x in selected.itertuples()],
        wc_to_next_gw_bb=sum((g+1 in result['bb_gws']) for g in wc),
        bb_following_wc=[int(g+1) for g in wc if g+1 in result['bb_gws']])
    (out/'summary.json').write_text(json.dumps(result,indent=2))
    print('FINAL_BB_FIT',json.dumps(result),flush=True)

if __name__=='__main__':main()
