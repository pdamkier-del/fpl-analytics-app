#!/usr/bin/env python3
"""Recover exact locked historical development bounds; never fit current quantiles."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_rolling_vfinal_gw6_38 import bps_bounds
from run_bps_background_experiment import actual_background_ledger

def main():
    lo,hi=bps_bounds(None,actual_background_ledger())
    p=ROOT/'work/live-final-model/original_bps_development_bounds.json'
    p.parent.mkdir(parents=True,exist_ok=True)
    report=dict(lower=lo,upper=hi,source='run_rolling_vfinal_gw6_38.bps_bounds(original historical ledger)',
                quantiles=[.01,.99],current_season_used=False,new_parameters=False)
    p.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
