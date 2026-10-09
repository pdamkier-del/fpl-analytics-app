#!/usr/bin/env python3
"""Conditional GW6–38 Bench Boost holdout using locked FH/WC and prior-season forecasts."""
import argparse,json
from pathlib import Path
import pandas as pd
import run_joint_fh_wc_stopping_replay as replay
import run_wc_ts_2024_conditional as historical
from fpl_xpts.simple_chip_thresholds import LOCKED_LAMBDA_FH,LOCKED_LAMBDA_WC

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--derived',required=True)
    p.add_argument('--vfinal',required=True)
    p.add_argument('--lambda-bb',type=float,required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names=historical.runtime_inputs(Path(a.derived))
    forecast=pd.read_csv(a.vfinal)
    forecast.id=forecast.id.astype(int)
    forecast['web_name']=forecast.id.map(names).fillna(forecast.id.astype(str))
    if 'team' not in forecast:forecast['team']=pd.NA
    r=replay.run('conditional_bb_'+str(a.lambda_bb),gws,names,forecast,
        use_chips=True,simple_thresholds=(LOCKED_LAMBDA_FH,LOCKED_LAMBDA_WC),
        start_gw=6,bb_lambda=a.lambda_bb)
    log=pd.DataFrame(r.pop('logs'));log.to_csv(out/'gameweeks.csv',index=False)
    r.update(lambda_bb=a.lambda_bb,
        bb_expected_incremental_xp=log.loc[log.chip.eq('bb'),'bb_gain'].tolist(),
        bb_actual_incremental_points=log.loc[log.chip.eq('bb'),'bb_realized_uplift'].tolist(),
        bb_bench_names=log.loc[log.chip.eq('bb'),'bb_bench_names'].tolist(),
        bb_after_wc=[g+1 for g in r['wc_gws'] if g+1 in r['bb_gws']])
    (out/'summary.json').write_text(json.dumps(r,indent=2))
    print('FINAL_BB_2024',json.dumps(r),flush=True)

if __name__=='__main__':main()
