#!/usr/bin/env python3
"""Run unchanged frozen BPS regression on externally verified 2026/27 ledger.

Strictly uses explicit 2026/27 pre-cutoff historical action/BPS rates. Never
calls historical 2025 loader; never replaces missing provider statistics by 0.
Produces BPS components, not a complete xP or a certified live release.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from run_bps_background_experiment import feature_frame,apply_model
from run_rolling_vfinal_gw6_38 import load_models

BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
WORK=ROOT/'work/live-final-model'
LEDGER_FIELDS=['player_uuid','available_at','minutes_played','bg_rate90','cross_rate90','cbi_rate90',
  'recovery_rate90','tackle_rate90','keypass_rate90','dribble_rate90','foulwon_rate90',
  'sot_rate90','passbps_rate90','negative_rate90']
def calculate(target,ledger,bps,bpsvar):
    required={'fixture_uuid','player_uuid','target_gw','cutoff','pos'}
    if missing:=required-set(target):raise ValueError('Missing BPS target fields '+str(sorted(missing)))
    if missing:=set(LEDGER_FIELDS)-set(ledger):
        raise ValueError('Missing verified 2026/27 BPS history fields '+str(sorted(missing)))
    if target.duplicated(['fixture_uuid','player_uuid']).any():
        raise ValueError('Duplicate BPS target player fixture')
    cutoff=pd.to_datetime(target.cutoff,utc=True,errors='raise')
    seen=pd.to_datetime(ledger.available_at,utc=True,errors='raise')
    if cutoff.nunique()!=1 or not (seen<cutoff.min()).all():
        raise ValueError('BPS input events not strictly pre-cutoff')
    for field in LEDGER_FIELDS:
        if field in ('player_uuid','available_at'):continue
        val=pd.to_numeric(ledger[field],errors='coerce')
        if not np.isfinite(val.to_numpy(float)).all():
            raise ValueError('Unverified BPS event data '+field)
    if (ledger.minutes_played<=0).any():raise ValueError('Invalid BPS played minute evidence')
    # Frozen add_history compares provider available_at with timezone-aware
    # cutoffs, so retain the parsed timestamps instead of raw CSV strings.
    target=target.copy();target['cutoff']=cutoff
    ledger=ledger.copy();ledger['available_at']=seen
    frame=feature_frame(target,3.,ledger)
    if missing:=set(bps['cols'])-set(frame):
        raise ValueError('Frozen BPS covariates missing '+str(sorted(missing)))
    means=apply_model(frame,bps)
    if not np.isfinite(means).all():raise ValueError('Invalid frozen BPS result')
    pos=target.pos.replace({'G':'GK','GKP':'GK'}).astype(str)
    sigma=bpsvar['position_sd90']
    if (~pos.isin(['GK','DEF','MID','FWD'])).any():raise ValueError('Invalid FPL BPS position')
    sd=np.array([float(sigma.get(p,bpsvar['global_sd90'])) for p in pos])
    if not np.isfinite(sd).all() or (sd<0).any():raise ValueError('Invalid frozen BPS variance')
    out=target[['fixture_uuid','player_uuid','target_gw']].copy()
    out['bg_mean_rate90']=means
    out['bg_sd90']=sd
    return out
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--target',type=Path,default=BASE/'vfinal_live_joined_inputs.csv.gz')
    p.add_argument('--ledger',type=Path,required=True)
    p.add_argument('--out',type=Path,default=BASE/'vfinal_live_bps_components.csv.gz')
    a=p.parse_args()
    models=load_models()
    out=calculate(pd.read_csv(a.target),pd.read_csv(a.ledger),models['bps'],models['bpsvar'])
    a.out.parent.mkdir(parents=True,exist_ok=True)
    out.to_csv(a.out,index=False,compression='gzip')
    WORK.mkdir(parents=True,exist_ok=True)
    report={'classification':'FROZEN_BPS_COMPONENT_ONLY_NO_LIVE_XP',
        'rows':len(out),'origin_gw':int(out.target_gw.min()),
        'model_math_unchanged':True,'locked_model_active':False,
        'note':'Pre-validated external BPS ledger required; provider equivalent source and 2026 score rules must be independently audited'}
    (WORK/'live_bps_component_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
if __name__=='__main__':main()
