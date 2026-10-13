#!/usr/bin/env python3
"""Descriptive calibration summaries; no model fitting or acceptance thresholds."""
import argparse,json
from pathlib import Path
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/full-model-audit-20261012'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--seasons',nargs='+',default=['2024-25','2025-26']);args=ap.parse_args();results={}
 for season in args.seasons:
  f=pd.read_csv(OUT/f'correctness_{season}_predictions.csv.gz');modes={}
  for mode,g in f.groupby('mode'):
   g=g.copy();g['probability_bin']=np.minimum(9,np.floor(g.start_probability*10).astype(int))
   bins=g.groupby('probability_bin').agg(rows=('started','size'),mean_predicted=('start_probability','mean'),actual_rate=('started','mean')).reset_index()
   ece=float((bins.rows*abs(bins.mean_predicted-bins.actual_rate)).sum()/bins.rows.sum())
   modes[mode]=dict(rows=len(g),mean_xp=float(g.xp.mean()),mean_actual_points=float(g.total_points.mean()),point_mean_bias=float((g.xp-g.total_points).mean()),start_ece_10_bins=ece,start_calibration_bins=bins.to_dict('records'),by_position={str(pos):dict(rows=len(s),point_mean_bias=float((s.xp-s.total_points).mean()),start_brier=float(((s.start_probability-s.started)**2).mean()),point_mae=float(abs(s.xp-s.total_points).mean())) for pos,s in g.groupby('pos')})
  r=json.loads((OUT/f'correctness_{season}_report.json').read_text());d=r['marginal_diagnostics'];teams=[t for fixture in d for t in fixture['teams'].values()]
  results[season]=dict(modes=modes,maximum_player_start_probability_adjustment=max(t['max_abs_marginal_change'] for t in teams),average_capped_cameos_per_match=float(np.mean([x['mean_cameos_capped_per_draw'] for x in d])),average_rejected_cameos_per_match=float(np.mean([x['mean_cameos_rejected_per_draw'] for x in d])),failed_fixture_modes=r['failed_fixture_modes'])
 report=dict(classification='DESCRIPTIVE_REUSED_PERIOD_CALIBRATION_NOT_CERTIFICATION',results=results,bin_definition='ten equal-width start-probability bins, p=1 included in last bin; descriptive only',promotion_allowed=False,locked_model_active=False)
 (OUT/'correctness_calibration_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({s:{'modes':{m:{k:v for k,v in values.items() if k not in ['by_position','start_calibration_bins']} for m,values in r['modes'].items()},'max_start_adjustment':r['maximum_player_start_probability_adjustment'],'average_capped_cameos':r['average_capped_cameos_per_match'],'average_rejected_cameos':r['average_rejected_cameos_per_match']} for s,r in results.items()},indent=2))
if __name__=='__main__':main()
