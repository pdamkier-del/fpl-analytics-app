#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from dataclasses import replace
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import run_transfer_strategy_v3_replay as ts
import run_horizon_policy_comparison as hp
from fpl_xpts.chip_planner import optimize_free_hit_squad
from fpl_xpts.fh_transfer_planner import _state_before_target
from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import actual_team_points,initial_squad,legalize_team_limit,valid_squad
from fpl_xpts.transfer_planner import PlannerConfig,plan_transfer_path,execute_first_action,clone_state,_apply_selected_squad

WEIGHTS=(1.0,.60,.36,.216,.1296,.07776)
BUFFER=1.0

EXPECTED_BEST_REMAINING={
    1:21.475,2:21.475,3:21.475,4:21.475,5:19.750,6:17.850,7:17.725,8:17.325,
    9:13.350,10:13.350,11:13.350,12:13.350,13:13.350,14:13.350,15:13.350,
    16:10.050,17:9.425,18:9.425,19:0.0,
    20:18.825,21:18.825,22:18.825,23:18.825,24:18.025,25:18.025,26:17.375,
    27:16.050,28:12.700,29:10.150,30:10.150,31:8.850,32:8.850,33:7.300,
    34:4.625,35:2.000,36:1.475,37:0.0,38:0.0,
}

def cfg():
    return PlannerConfig(weights=WEIGHTS,hit_uncertainty_buffer=BUFFER,beam_width=20,
        candidates_per_transfer_count=1,candidate_limit_per_position=18,
        top_targets_per_position=18,local_bundle_beam=60,candidate_return_per_depth=12,
        max_transfers_per_week=5,candidate_backend='fast_local',milp_time_limit=2.0)

def load(vfinal):
    gws,names,cold=ts.prepare()
    cold=cold[cold.origin_gw<=4].copy()
    vf=pd.read_csv(vfinal)
    vf['web_name']=vf.id.astype(int).map(names).fillna(vf.id.astype(str))
    keep=['id','web_name','position','gw','origin_gw','xpts_mean','p_play','fixtures']
    vf=vf[keep].copy();vf.id=vf.id.astype(int)
    return gws,names,pd.concat([cold[keep],vf],ignore_index=True)


from fpl_xpts.wildcard_planner_v2 import optimize_wildcard

def run(label,gws,names,forecast,wc_gw=None,bench_value=.16):
    meta1=hp.gw_meta(gws,names,1)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    state=initial_squad(origin1,meta1,[1])
    known=meta1.copy();total=0;logs=[];pcfg=cfg()
    for gw in range(1,39):
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin_raw=forecast[forecast.origin_gw==gw-1].copy()
        current=hp.complete_current_projection(origin_raw,meta,gw)
        origin=ts.origin_with_meta(forecast,meta,gw)
        forced=legalize_team_limit(state,meta,origin,gw) if gw>1 else []
        old_ft=int(state.free_transfers);old_bank=int(state.bank)
        old_squad=set(state.squad)
        wc=None
        if wc_gw==gw:
            wc=optimize_wildcard(state,meta,origin,gw,pcfg,forecast_history=forecast,bench_value=bench_value)
            state=wc.state
            if state.free_transfers!=old_ft:raise AssertionError('Wildcard corrupted FT')
            if not valid_squad(meta,state.squad):raise AssertionError('Illegal WC result')
            hit=0;transfers=wc.changed
        else:
            normal=plan_transfer_path(state,meta,origin,gw,pcfg)
            moves=execute_first_action(state,normal,meta)
            hit=sum(int(x.get('hit',0)) for x in moves)+sum(int(x.get('hit',0)) for x in forced)
            transfers=len(moves)+len(forced)
        plan=plan_squad(current,list(state.squad),gw)
        score,_=actual_team_points(plan.rows,hp.actual_gw(gws,gw),None,hit)
        total+=int(score)
        logs.append(dict(gw=gw,score=int(score),cumulative=int(total),wildcard=wc is not None,
                         transfers=int(transfers),hit_cost=int(hit),free_transfers=int(state.free_transfers),
                         bank_tenths=int(state.bank),squad_ids=';'.join(map(str,sorted(state.squad))),
                         wc_gain=(float(wc.gain) if wc else None),
                         wc_budget=(int(wc.budget_tenths) if wc else None),
                         wc_normal_q=(float(wc.normal_objective) if wc else None),
                         wc_action_q=(float(wc.wildcard_objective) if wc else None),
                         wc_retained=(15-wc.changed if wc else None),
                         wc_price_advantage_tenths=(wc.effective_price_savings_tenths if wc else None),
                         wc_projection_gws=(wc.projected_gws if wc else None),
                         wc_old_squad=(';'.join(map(str,sorted(old_squad))) if wc else None)))
        print(label,gw,score,total,'WC',wc is not None,flush=True)
    return dict(label=label,total_points=total,wildcard_gw=wc_gw,
                transfers=sum(x['transfers'] for x in logs),
                hit_points=sum(x['hit_cost'] for x in logs),logs=logs)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--vfinal',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names,forecast=load(a.vfinal)
    results={}
    for name,gw,bench in [('baseline',None,.16),('wc_v2_gw6',6,.16),('wc_v2_gw20',20,.16),('wc_v2_gw20_no_bench',20,0.)]:
        z=run(name,gws,names,forecast,gw,bench_value=bench)
        pd.DataFrame(z.pop('logs')).to_csv(out/(name+'.csv'),index=False)
        results[name]=z
    if results['baseline']['total_points']!=2125:
        raise AssertionError('Locked baseline drift: '+str(results['baseline']['total_points']))
    (out/'summary.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))
if __name__=='__main__':main()
