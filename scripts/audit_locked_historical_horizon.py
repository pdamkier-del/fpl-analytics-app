#!/usr/bin/env python3
"""Inspect the checksum-pinned benchmark artifact without changing its score."""
import sys,json
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.forecast_horizon_contract import horizon_report
OUT=ROOT/'analysis/results/full-model-audit-20261012'
def main():
 b=OUT/'locked-2125';f=pd.read_csv(b/'rolling-vfinal-final-gw6-38/rolling_vfinal_forecast.csv.gz');report=horizon_report(f)
 l=pd.read_csv(b/'final-locked-chain-gw1-38/gameweek_log.csv');assert int(l.score.sum())==2125
 report.update(benchmark_points=int(l.score.sum()),hit_points=int(l.hit_cost.sum()),transfers=int(l.transfers.sum()),workflow=37612845586,artifact_id=11480605718,artifact_sha256='78127ec480c119d95a60fabab7d3575e7690f304defef1b365831204f6e5cea6')
 m=pd.read_csv(b/'locked-mm-final-gw6-38/locked_mm_predictions.csv.gz');prob=m.new_p_start.to_numpy();y=m.y.to_numpy()
 report['locked_mm_diagnostic']={'rows':len(m),'gws':sorted(map(int,m.gw.unique())),'start_brier':float(np.mean((prob-y)**2)),'start_log_loss':float(-np.mean(y*np.log(np.clip(prob,1e-9,1))+(1-y)*np.log(np.clip(1-prob,1e-9,1)))),'xmins_mae':float(np.mean(abs(m.new_xmins-m.minutes))),'xmins_rmse':float(np.sqrt(np.mean((m.new_xmins-m.minutes)**2))),'warning':'archived reused walk-forward predictions, no independent promotion claim'}
 (OUT/'historical_horizon_report.json').write_text(json.dumps(report,indent=2)+'\n');print('Benchmark preserved',report['benchmark_points'],'horizon cells',report['actual_origin_target_pairs'],'/',report['required_origin_target_pairs'])
if __name__=='__main__':main()
