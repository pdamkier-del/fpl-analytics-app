#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import run_joint_fh_wc_stopping_replay as base
from joint_chip_historical_priors import calibrated_assumptions

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--vfinal',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--structural',required=True)
    ap.add_argument('--availability',required=True)
    ap.add_argument('--wc-history',required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    params,manifest=calibrated_assumptions(a.availability,a.wc_history)
    gws,names,forecast=base.load(a.vfinal)
    structural=pd.read_csv(a.structural)
    baseline=base.run('baseline',gws,names,forecast)
    pd.DataFrame(baseline.pop('logs')).to_csv(out/'baseline.csv',index=False)
    assert baseline['total_points']==2125
    policy=base.run('joint_calibrated',gws,names,forecast,True,params,structural)
    pd.DataFrame(policy.pop('logs')).to_csv(out/'joint_calibrated.csv',index=False)
    result=dict(baseline=baseline,policy=policy,delta=int(policy['total_points'])-2125,
                calibration=manifest)
    (out/'summary.json').write_text(json.dumps(result,indent=2))
    print('CALIBRATED_FINAL',json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
