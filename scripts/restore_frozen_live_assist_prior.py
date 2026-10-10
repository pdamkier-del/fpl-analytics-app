#!/usr/bin/env python3
"""Restore EXACT historical assist-per-goal ratio for current vFinal fixture frame.

Same formula as scripts/run_rolling_vfinal_gw6_38.py; never use target fixture
results, fabricate an assist total, or refit a regression.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
WORK=ROOT/'work/live-final-model'
def derive(frame,history):
    required={'cutoff','fixture_uuid','player_uuid'}
    evidence={'available_at','goals','fpl_assists'}
    if missing:=required-set(frame):raise ValueError('Missing target columns '+str(sorted(missing)))
    if missing:=evidence-set(history):raise ValueError('Missing source assist evidence '+str(sorted(missing)))
    cuts=pd.to_datetime(frame.cutoff,utc=True,errors='raise')
    if cuts.isna().any() or cuts.nunique()!=1:raise ValueError('Mixed/invalid target cutoff')
    observed=pd.to_datetime(history.available_at,utc=True,errors='raise')
    if observed.isna().any() or not (observed<cuts.min()).all():
        raise ValueError('Historic assist data includes target-future observations')
    for col in ('goals','fpl_assists'):
        num=pd.to_numeric(history[col],errors='coerce')
        if not np.isfinite(num.to_numpy(float)).all() or (num<0).any():
            raise ValueError('Missing/invalid actual '+col)
    g=float(history.goals.sum())
    ratio=min(1.,max(.5,float(history.fpl_assists.sum())/g)) if g>0 else .7
    if 'assist_probability_per_goal' in frame:
        if not np.allclose(frame.assist_probability_per_goal.to_numpy(float),ratio,rtol=0,atol=1e-12):
            raise ValueError('Conflicting existing assist probability')
        out=frame.copy()
    else:
        out=frame.assign(assist_probability_per_goal=ratio)
    return out,{'locked_formula':'min(1,max(.5,sum(fpl_assists)/sum(goals))) if goals>0 else .7',
                'observed_goals':g,'observed_assists':float(history.fpl_assists.sum()),
                'historical_rows':len(history),'assist_probability_per_goal':ratio,
                'target_outcomes_used':False,'locked_model_math_unchanged':True}
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--base',type=Path,default=BASE/'vfinal_live_joined_inputs.csv.gz')
    p.add_argument('--history',type=Path,default=BASE/'player_fixture_observations.csv.gz')
    p.add_argument('--out',type=Path,default=BASE/'vfinal_live_joined_inputs.csv.gz')
    a=p.parse_args()
    frame=pd.read_csv(a.base,low_memory=False)
    history=pd.read_csv(a.history,low_memory=False)
    result,audit=derive(frame,history)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    result.to_csv(a.out,index=False,compression='gzip')
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/'live_assist_prior_provenance.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(audit))
if __name__=='__main__':main()
