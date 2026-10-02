#!/usr/bin/env python3
"""Produce experimental forecasts from pre-cutoff features without outcomes."""
import argparse
import json
from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.frozen_forecast import predict_frozen,VARIANTS
from build_reproducible_role_benchmark import write_prediction_csv


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--features',required=True)
    ap.add_argument('--models',default=str(ROOT/'analysis/results/workload-minutes-v1/frozen_models.json'))
    ap.add_argument('--protocol',default=str(ROOT/'analysis/results/workload-minutes-v1/protocol.json'))
    ap.add_argument('--variant',choices=list(VARIANTS),default='workload_start')
    ap.add_argument('--out',required=True)
    a=ap.parse_args();protocol=json.loads(Path(a.protocol).read_text())
    frame=pd.read_csv(a.features)
    result=predict_frozen(frame,json.loads(Path(a.models).read_text()),protocol['final_fit']['training_cutoff'],a.variant)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    if out.suffix=='.gz':write_prediction_csv(result,out)
    else:result.to_csv(out,index=False)
    print({'rows':len(result),'variant':a.variant,'experimental':True,'output':str(out)})


if __name__=='__main__':main()
