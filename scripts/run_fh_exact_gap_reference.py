#!/usr/bin/env python3
from __future__ import annotations
import argparse,gzip,json,sys
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_horizon_policy_comparison as hp
from fpl_xpts.chip_planner import optimize_free_hit_squad
from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import initial_squad,legalize_team_limit,valid_squad
from fpl_xpts.transfer_planner import PlannerConfig,execute_first_action,plan_transfer_path
from run_2024_25_conditional_ts_gw6_38 import runtime_inputs,origin_with_meta,WEIGHTS,BUFFER

def expected_empirical_max(values,n):
    if n<=0 or len(values)==0:return 0.0
    x=np.sort(np.asarray(values,float))
    m=len(x);out=0.0;prev=0.0
    for i,v in enumerate(x,1):
        f=i/m
        p=f**n-prev**n
        out+=float(v)*p
        prev=f
    return float(out)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--derived',required=True)
    ap.add_argument('--vfinal',required=True)
    ap.add_argument('--out',required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)

    gws,names=runtime_inputs(Path(a.derived))
    forecast=pd.read_csv(a.vfinal);forecast.id=forecast.id.astype(int)
    forecast['web_name']=forecast.id.map(names).fillna(forecast.id.astype(str))
    meta=hp.gw_meta(gws,names,6)
    origin0=hp.complete_current_projection(forecast[forecast.origin_gw==5],meta,6)
    state=initial_squad(origin0,meta,[6])
    known=meta.copy()
    cfg=PlannerConfig(weights=WEIGHTS,hit_uncertainty_buffer=BUFFER,beam_width=20,
        candidates_per_transfer_count=1,candidate_limit_per_position=18,top_targets_per_position=18,
        local_bundle_beam=60,candidate_return_per_depth=12,max_transfers_per_week=5,
        candidate_backend='fast_local',milp_time_limit=2.0)

    rows=[]
    for gw in range(6,39):
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin_raw=forecast[forecast.origin_gw==gw-1].copy()
        current=hp.complete_current_projection(origin_raw,meta,gw)
        origin=origin_with_meta(forecast,meta,gw)
        if gw>6:legalize_team_limit(state,meta,origin,gw)
        result=plan_transfer_path(state,meta,origin,gw,cfg)
        execute_first_action(state,result,meta)
        if not valid_squad(meta,state.squad):raise RuntimeError(f'invalid squad GW{gw}')
        normal=plan_squad(current,list(state.squad),gw)
        normal_xp=float(normal.expected_score)
        fh=optimize_free_hit_squad(state=state,meta=meta,forecast=origin,gw=gw,normal_score=normal_xp)
        gap=float(fh['fh_gain'])
        rows.append(dict(gw=gw,half=(1 if gw<=19 else 2),normal_xp=normal_xp,fh_xp=float(fh['fh_score']),fh_gap=gap))
        print(f'2024/25 GW{gw}: normal={normal_xp:.3f} FH={fh["fh_score"]:.3f} gap={gap:.3f}',flush=True)

    raw=pd.DataFrame(rows)
    refs=[]
    for gw in range(1,39):
        half=1 if gw<=19 else 2
        end=19 if half==1 else 38
        n=max(0,end-gw)
        pool=raw.loc[raw.half.eq(half),'fh_gap'].to_numpy(float)
        refs.append(dict(gw=gw,half=half,n_remaining=n,pool_size=len(pool),
                         expected_best_remaining_gap=expected_empirical_max(pool,n),
                         historical_mean_gap=float(np.mean(pool)),
                         historical_median_gap=float(np.median(pool)),
                         historical_max_gap=float(np.max(pool))))
    ref=pd.DataFrame(refs)
    raw.to_csv(out/'historical_exact_fh_gaps_2024_25.csv',index=False)
    ref.to_csv(out/'expected_best_remaining_reference.csv',index=False)
    summary={'classification':'2024/25 exact raw FH gap reference against replayed TS squad',
             'metric':'FH optimized XI+captain xP minus normal TS XI+captain xP',
             'reference':'Expected maximum of n remaining draws from same-half empirical 2024/25 raw-gap distribution',
             'realised_points_used':False,'rows':len(raw)}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
