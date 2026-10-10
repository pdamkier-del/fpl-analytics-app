#!/usr/bin/env python3
"""Run original locked vFinal joint simulator only on COMPLETE live fixture inputs.

No 2025-26 score checkpoints, no refit, no FPL ep_next substitutes. Intended
input is the fully composed fixture table after upstream current-year features.
This script never certifies MM/TS/chips or publishes app output.
"""
from __future__ import annotations
import argparse,hashlib,json,sys
from dataclasses import replace
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.paired_joint import build_pair
from fpl_v1_1_model.joint_simulator import simulate_many
from run_vfinal_integrated import make_vfinal_input

BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
WORK=ROOT/'work/live-final-model'
REQUIRED={
 'fixture_uuid','player_uuid','team_id','target_gw','pos','cutoff',
 'home_team_id','away_team_id','lambda_home_goals','lambda_away_goals',
 'assist_probability_per_goal','control_p_start','control_xmins',
 'p_cameo_given_bench','start_minutes_mean','cameo_minutes_mean',
 'v4_workload_start_p_start','v4_workload_start_xmins',
 'v4_p_cameo_given_bench','v4_start_minutes_mean','v4_cameo_minutes_mean',
 'goal_mu','assist_mu','mu_dc','dc_alpha','p_yellow','p_red','lambda_saves',
 'lambda_pen','pen_weight','pen_conversion','team_pen_conversion',
 'bg_mean_rate90','bg_sd90'
}
def validate(frame):
    missing=sorted(REQUIRED-set(frame))
    if missing:raise ValueError('Missing frozen simulator fields: '+', '.join(missing))
    if frame.empty or frame.duplicated(['fixture_uuid','player_uuid']).any():
        raise ValueError('Empty/duplicate fixture players')
    if frame.cutoff.nunique()!=1 or frame.target_gw.nunique()>6:
        raise ValueError('Mixed as-of cutoffs or horizon > six gameweeks')
    nums=sorted(REQUIRED-{'fixture_uuid','player_uuid','pos','cutoff'})
    for c in nums:
        v=pd.to_numeric(frame[c],errors='coerce').to_numpy(float)
        if not np.isfinite(v).all():raise ValueError('Nonfinite simulator field '+c)
    gws=sorted(set(int(x) for x in frame.target_gw))
    if gws!=list(range(gws[0],gws[-1]+1)):
        raise ValueError('Nonconsecutive forecast horizon')
    for fx,g in frame.groupby('fixture_uuid'):
        if len(g)<22 or g.team_id.nunique()!=2:
            raise ValueError('Incomplete real fixture rosters '+str(fx))
        if set(g.team_id.astype(int))!={int(g.home_team_id.iloc[0]),int(g.away_team_id.iloc[0])}:
            raise ValueError('Wrong fixture team sides')
        if (g.groupby('team_id').size()<11).any():raise ValueError('Incomplete team XI candidates')
        for col in ('lambda_pen','team_pen_conversion'):
            if (g.groupby('team_id')[col].nunique()!=1).any():
                raise ValueError('Inconsistent team penalty source '+col)
        pw=g.groupby('team_id').pen_weight.sum()
        if not np.allclose(pw,1.,rtol=0,atol=1e-6):
            raise ValueError('Penalty weight mass not normalized')
        for c in ('p_start','p_cameo_given_bench','pen_weight','pen_conversion'):
            real='control_p_start' if c=='p_start' else c
            if not g[real].between(0,1).all():raise ValueError('Invalid probability '+c)
    return {'fixtures':frame.fixture_uuid.nunique(),'players':len(frame),'gws':gws}

def simulate(frame,draws=400,seed=93000000):
    audit=validate(frame)
    rows=[]
    for i,(fx,g) in enumerate(frame.groupby('fixture_uuid',sort=True)):
        # make_vfinal_input imports original frozen event simulator adapter.
        inp,_=make_vfinal_input(g.copy())
        # Live 2026/27 scoring rules must supersede historical backtest rules.
        inp=replace(inp,bps_rules='2026-27')
        sim=simulate_many(inp,n=draws,seed=seed+i)
        expected=set(g.player_uuid.astype(str))
        if set(sim)!=expected:raise ValueError('Simulator missed player identities')
        gw=int(g.target_gw.iloc[0])
        for pid in sorted(expected):
            s=sim[pid]
            x=float(s['xPts'])
            if not np.isfinite(x):raise ValueError('Nonfinite simulated xPts')
            rows.append({'fixture_uuid':fx,'player_uuid':pid,'gw':gw,
                         'xpts_fixture':x,'expected_minutes':float(s['expected_minutes']),
                         'expected_bonus':float(s['expected_bonus'])})
    audit.update({'classification':'LOCKED_VFINAL_SIMULATED_DIAGNOSTIC_NOT_CHAIN_CERTIFIED',
                  'draws_per_fixture':draws,'xpts_calculated':True,
                  'locked_model_active':False,'ts_and_chips_ran':False})
    return pd.DataFrame(rows),audit

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--out',type=Path,default=BASE/'live_vfinal_fixture_xp.csv.gz')
    p.add_argument('--draws',type=int,default=400)
    a=p.parse_args()
    if a.draws!=400:raise ValueError('Locked Monte Carlo draws are exactly 400')
    frame=pd.read_csv(a.input,low_memory=False)
    predicted,audit=simulate(frame,draws=a.draws)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    predicted.to_csv(a.out,index=False,compression='gzip')
    WORK.mkdir(parents=True,exist_ok=True)
    audit['source_sha256']=hashlib.sha256(a.input.read_bytes()).hexdigest()
    (WORK/'live_vfinal_simulation_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(audit))
if __name__=='__main__':main()
