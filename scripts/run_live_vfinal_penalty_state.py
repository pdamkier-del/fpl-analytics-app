#!/usr/bin/env python3
"""Apply the original frozen penalty-state function to 2026/27 live inputs.

Inputs MUST be verified historical events, not FPL season aggregates. No
penalty events in GW >= origin may be included, and no new parameters are fit.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.vfinal_replay_state import penalty_state
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
WORK=ROOT/'work/live-final-model'
MODEL=ROOT/'analysis/results/shared-penalty-model-20261005-v1/model_summary.json'

def apply(roster,attempts,sides,teams,summary,origin):
    if origin<2:raise ValueError('Origin must have historical GW')
    required=[(roster,{'player_uuid','team_id','fixture_uuid','opponent_team_id','goal_rate90'}),
      (attempts,{'player_uuid','gw','attempts','penalties_scored','available_at'}),
      (sides,{'gw','team_code','opp_code','attempts','available_at'}),
      (teams,{'team_code','team_id'})]
    for df,cols in required:
        if missing:=cols-set(df):raise ValueError('Missing frozen penalty-state inputs '+str(sorted(missing)))
    if attempts.gw.ge(origin).any() or sides.gw.ge(origin).any():
        raise ValueError('Future penalty event in historical state')
    if (attempts.attempts<attempts.penalties_scored).any() or (attempts.penalties_scored<0).any():
        raise ValueError('Invalid recorded penalty outcome')
    if roster.duplicated(['fixture_uuid','player_uuid']).any():
        raise ValueError('Duplicate player fixture in live targets')
    team_map=dict(zip(teams.team_code.astype(int),teams.team_id.astype(int)))
    if len(team_map)!=len(teams):raise ValueError('Ambiguous team identity map')
    ps,lam=penalty_state(origin,roster, sides,attempts,team_map,summary)
    result=roster[['fixture_uuid','player_uuid','team_id','opponent_team_id','goal_rate90']].copy()
    result['pen_attempt_state']=[ps[str(p)][0] for p in result.player_uuid]
    result['pen_conversion']=[ps[str(p)][1] for p in result.player_uuid]
    result['lambda_pen']=[lam(int(t),int(o)) for t,o in zip(result.team_id,result.opponent_team_id)]
    result['pen_weight_raw']=result.pen_attempt_state+.02*np.maximum(result.goal_rate90,1e-6)
    denom=result.groupby(['fixture_uuid','team_id']).pen_weight_raw.transform('sum')
    if (denom<=0).any():raise ValueError('Invalid penalty taker denominator')
    result['pen_weight']=result.pen_weight_raw/denom
    result['team_pen_conversion']=(result.pen_weight*result.pen_conversion).groupby(
        [result.fixture_uuid,result.team_id]).transform('sum')
    numerical=['pen_conversion','lambda_pen','pen_weight','team_pen_conversion']
    if not np.isfinite(result[numerical].to_numpy(float)).all():
        raise ValueError('Nonfinite frozen penalty input')
    return result[['fixture_uuid','player_uuid','team_id','lambda_pen','pen_weight',
                   'pen_conversion','team_pen_conversion']]

def main():
    p=argparse.ArgumentParser();p.add_argument('--origin',type=int,required=True)
    p.add_argument('--attempts',type=Path,required=True)
    p.add_argument('--sides',type=Path,required=True)
    p.add_argument('--teams',type=Path,required=True)
    p.add_argument('--roster',type=Path,default=BASE/'vfinal_live_joined_inputs.csv.gz')
    args=p.parse_args()
    inputs=[pd.read_csv(path) for path in [args.roster,args.attempts,args.sides,args.teams]]
    cutoff=pd.to_datetime(pd.read_csv(args.roster,usecols=['cutoff']).cutoff,utc=True).min()
    for name,history in zip(['attempts','sides'],inputs[1:3]):
        observed=pd.to_datetime(history.available_at,utc=True,errors='raise')
        if not (observed<cutoff).all():raise ValueError(name+': post-cutoff penalty data')
    model=json.loads(MODEL.read_text())
    result=apply(*inputs,model,args.origin)
    out=BASE/'vfinal_live_penalty_inputs.csv.gz'
    result.to_csv(out,index=False,compression='gzip')
    audit={'status':'FROZEN_PENALTY_INPUT_ONLY_NOT_VFINAL_XP',
        'origin_gw':args.origin,'rows':len(result),
        'frozen_function':'vfinal_replay_state.penalty_state',
        'xpts_calculated':False,'live_certified':False}
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/'live_penalty_component_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(audit))
if __name__=='__main__':main()
