#!/usr/bin/env python3
"""Run one cutoff-aware 2025/26 FH/WC threshold pair with locked TS."""
import argparse,json
from pathlib import Path
import pandas as pd
import run_joint_fh_wc_stopping_replay as replay

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--vfinal',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--lambda-fh',type=float,required=True)
    ap.add_argument('--lambda-wc',type=float,required=True)
    a=ap.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names,forecast=replay.load(a.vfinal)
    result=replay.run('simple_wc_fh',gws,names,forecast,
        use_chips=True,simple_thresholds=(a.lambda_fh,a.lambda_wc))
    pd.DataFrame(result.pop('logs')).to_csv(out/'gameweeks.csv',index=False)
    result.update(lambda_fh=a.lambda_fh,lambda_wc=a.lambda_wc,
                  delta_from_locked=result['total_points']-2125)
    (out/'summary.json').write_text(json.dumps(result,indent=2))
    print('FINAL_SIMPLE_CHIPS',json.dumps(result),flush=True)
if __name__=='__main__':main()
