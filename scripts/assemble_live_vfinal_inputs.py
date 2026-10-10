#!/usr/bin/env python3
"""Compose current-season vFinal fixture rows from existing frozen components.

Fail closed: raw rate90 and total xG are NOT simulation goal_mu. Preserve
the exact frozen normalized_mu allocation from run_vfinal_integrated.
Additional priors must already be computed by the historical locked pipeline.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_vfinal_integrated import normalized_mu
from run_live_vfinal_joint_simulation import validate
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
WORK=ROOT/'work/live-final-model'
KEY=['fixture_uuid','player_uuid']
REQUIRED_BASE={
  'p_start','xmins','mm_q_sub','mm_sub_minutes',
  'assist_probability_per_goal','goal_rate90','assist_rate90','dc_alpha',
  'p_yellow','p_red','cutoff','target_gw','pos','team_id','lambda_saves'
}
def assemble(base,pen,bps):
    if missing:=REQUIRED_BASE-set(base):
        raise ValueError('Missing upstream frozen live features: '+', '.join(sorted(missing)))
    result=base.copy()
    for name,extra,cols in [
      ('penalties',pen,['lambda_pen','pen_weight','pen_conversion','team_pen_conversion']),
      ('bps',bps,['bg_mean_rate90','bg_sd90'])]:
        if extra.duplicated(KEY).any():raise ValueError(name+' has duplicate identities')
        if set(map(tuple,result[KEY].astype(str).to_numpy()))!=set(map(tuple,extra[KEY].astype(str).to_numpy())):
            raise ValueError(name+' player-fixture identities differ')
        if any(x in result for x in cols):raise ValueError('Component name collision '+name)
        result=result.merge(extra[KEY+cols],on=KEY,how='inner',validate='one_to_one')
    # Recover exactly the locked conditional-starter identity rather than
    # inventing an unobserved starter duration. At p_start=0, this is
    # mathematically unidentified and must be explicit source evidence.
    if 'start_minutes_mean' not in result:
        raise ValueError('Missing locked conditional starter minutes: cannot infer from xmins alone for zero-start players')
    # No approximation: the original Phase 4B candidate requires the
    # minute identity and explicit start/cameo conditional durations.
    result['control_p_start']=result.p_start
    result['control_xmins']=result.xmins
    result['p_cameo_given_bench']=result.mm_q_sub
    result['cameo_minutes_mean']=result.mm_sub_minutes
    result['v4_workload_start_p_start']=result.p_start
    result['v4_workload_start_xmins']=result.xmins
    result['v4_p_cameo_given_bench']=result.mm_q_sub
    result['v4_start_minutes_mean']=result.start_minutes_mean
    result['v4_cameo_minutes_mean']=result.mm_sub_minutes
    # Existing penalty/BPS components are only applied at their exact model
    # boundary. These two original functions normalize team scoring shares.
    if 'goal_mu' not in result: result['goal_mu']=normalized_mu(result,result.goal_rate90.to_numpy(float),assist=False)
    if 'assist_mu' not in result: result['assist_mu']=normalized_mu(result,result.assist_rate90.to_numpy(float),assist=True)
    validate(result)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--base',type=Path,default=BASE/'vfinal_live_joined_inputs.csv.gz')
    p.add_argument('--penalty',type=Path,default=BASE/'vfinal_live_penalty_inputs.csv.gz')
    p.add_argument('--bps',type=Path,default=BASE/'vfinal_live_bps_components.csv.gz')
    p.add_argument('--out',type=Path,default=BASE/'vfinal_live_full_simulator_input.csv.gz')
    a=p.parse_args()
    joined=assemble(pd.read_csv(a.base),pd.read_csv(a.penalty),pd.read_csv(a.bps))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    joined.to_csv(a.out,index=False,compression='gzip')
    WORK.mkdir(parents=True,exist_ok=True)
    report={'classification':'COMPLETE_LIVE_INPUT_READY_FOR_FROZEN_SIMULATOR_NOT_FULL_CHAIN_CERTIFIED',
            'rows':len(joined),'gws':sorted(map(int,joined.target_gw.unique())),
            'xp_generated':False,'locked_model_active':False}
    (WORK/'live_vfinal_full_input_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
if __name__=='__main__':main()

