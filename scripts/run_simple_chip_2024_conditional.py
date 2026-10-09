#!/usr/bin/env python3
"""Conditional 2024/25 GW6-38 chip validation (not comparable to full-season 2025/26)."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import run_joint_fh_wc_stopping_replay as replay
import run_wc_ts_2024_conditional as hist

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--derived',required=True)
    ap.add_argument('--vfinal',required=True)
    ap.add_argument('--out',required=True)
    a=ap.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names=hist.runtime_inputs(Path(a.derived))
    forecast=pd.read_csv(a.vfinal)
    forecast.id=forecast.id.astype(int)
    forecast['web_name']=forecast.id.map(names).fillna(forecast.id.astype(str))
    if 'team' not in forecast:forecast['team']=pd.NA
    baseline=replay.run('conditional_locked_baseline',gws,names,forecast,start_gw=6)
    pd.DataFrame(baseline.pop('logs')).to_csv(out/'baseline.csv',index=False)
    results=[]
    for fh,wc in [(5,20),(10,20),(15,20),(10,25)]:
        result=replay.run(f'conditional_fh{fh}_wc{wc}',gws,names,forecast,
            use_chips=True,simple_thresholds=(fh,wc),start_gw=6)
        pd.DataFrame(result.pop('logs')).to_csv(out/f'fh{fh}_wc{wc}.csv',index=False)
        results.append(dict(lambda_fh=fh,lambda_wc=wc,**result))
    summary=dict(baseline=baseline,policies=results)
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print('CONDITIONAL_2024_SIMPLE',json.dumps(summary),flush=True)
if __name__=='__main__':main()
