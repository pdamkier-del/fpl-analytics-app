#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_transfer_strategy_v3_replay as ts
import run_horizon_policy_comparison as hp
from fpl_xpts.fh_transfer_planner import evaluate_fh_aware_path
from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import actual_team_points,initial_squad,legalize_team_limit,valid_squad
from fpl_xpts.transfer_planner import PlannerConfig,plan_transfer_path,execute_first_action

WEIGHTS=(1.0,.60,.36,.216,.1296,.07776)
BUFFER=1.0

def planner_config():
    return PlannerConfig(weights=WEIGHTS,hit_uncertainty_buffer=BUFFER,beam_width=20,
        candidates_per_transfer_count=1,candidate_limit_per_position=18,
        top_targets_per_position=18,local_bundle_beam=60,candidate_return_per_depth=12,
        max_transfers_per_week=5,candidate_backend='fast_local',milp_time_limit=2.0)

def load_forecast(vfinal):
    gws,names,cold=ts.prepare()
    cold=cold[cold.origin_gw<=4].copy()
    vf=pd.read_csv(vfinal)
    vf['web_name']=vf.id.astype(int).map(names).fillna(vf.id.astype(str))
    keep=['id','web_name','position','gw','origin_gw','xpts_mean','p_play','fixtures']
    vf=vf[keep].copy();vf.id=vf.id.astype(int)
    forecast=pd.concat([cold[keep],vf],ignore_index=True)
    return gws,names,forecast

def run_track(label,gws,names,forecast,fh_aware=False,allow_fh=False):
    meta1=hp.gw_meta(gws,names,1)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    state=initial_squad(origin1,meta1,[1])
    known=meta1.copy();total=0;logs=[];fh_used_halves=set()
    cfg=planner_config()

    for gw in range(1,39):
        t0=time.perf_counter()
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin_raw=forecast[forecast.origin_gw==gw-1].copy()
        current=hp.complete_current_projection(origin_raw,meta,gw)
        origin=ts.origin_with_meta(forecast,meta,gw)

        forced=[]
        if gw>1:
            forced=legalize_team_limit(state,meta,origin,gw)

        half=1 if gw<=19 else 2
        period_end=19 if half==1 else 38
        # Cold-start guardrail: GW1-5 have the least mature forecast/history and
        # the initial squad was just selected freely. This is explicit and is
        # tested separately from the bridge mathematics.
        min_fh_gw=6 if half==1 else 20
        chip_available=allow_fh and half not in fh_used_halves

        if fh_aware:
            ev=evaluate_fh_aware_path(
                state,meta,origin,gw,period_end_gw=period_end,min_fh_gw=min_fh_gw,
                config=cfg,allow_fh=chip_available,
            )
            result=ev.active_result
            recommended_fh_gw=ev.recommended_fh_gw
            use_fh_now=bool(ev.use_fh_now and chip_available)
            normal_obj=float(ev.normal_objective);active_obj=float(ev.active_objective)
            bridge_uplift=float(active_obj-normal_obj)
        else:
            result=plan_transfer_path(state,meta,origin,gw,cfg)
            recommended_fh_gw=None;use_fh_now=False
            normal_obj=float(result.objective);active_obj=float(result.objective);bridge_uplift=0.0

        # Current permanent-team counterfactual before any current deadline move.
        pre_plan=plan_squad(current,list(state.squad),gw)
        pre_score,_=actual_team_points(pre_plan.rows,hp.actual_gw(gws,gw),None,0)

        transfers=execute_first_action(state,result,meta)
        hit_cost=sum(int(x.get('hit',0)) for x in transfers)+sum(int(x.get('hit',0)) for x in forced)
        if not valid_squad(meta,state.squad):
            raise RuntimeError(f'{label} GW{gw}: invalid permanent squad')

        if use_fh_now:
            cand=next(x for x in ev.bridge_candidates if int(x.gw)==int(gw))
            score,_=actual_team_points(cand.fh_plan['plan_rows'],hp.actual_gw(gws,gw),'free_hit',0)
            fh_used_halves.add(half)
            fh_expected_score=float(cand.fh_score)
            fh_expected_bridge_uplift=float(cand.uplift_vs_no_fh)
            fh_squad=';'.join(map(str,cand.fh_plan['fh_squad_ids']))
            fh_cap=int(cand.fh_plan['fh_captain_id'])
            # By construction the bridge action contains zero permanent transfers
            # and preserves FT, so execute_first_action leaves persistent state intact.
        else:
            plan=plan_squad(current,list(state.squad),gw)
            score,_=actual_team_points(plan.rows,hp.actual_gw(gws,gw),None,hit_cost)
            fh_expected_score=None;fh_expected_bridge_uplift=None;fh_squad='';fh_cap=None

        total+=int(score)
        logs.append(dict(
            track=label,gw=gw,score=int(score),cumulative=int(total),
            transfers=len(transfers)+len(forced),forced_transfers=len(forced),hit_cost=int(hit_cost),
            bank=state.bank/10,free_transfers_after=state.free_transfers,
            fh_recommended_gw=recommended_fh_gw,fh_used=use_fh_now,
            fh_expected_score=fh_expected_score,fh_expected_bridge_uplift=fh_expected_bridge_uplift,
            fh_squad_ids=fh_squad,fh_captain_id=fh_cap,
            no_move_actual_points=int(pre_score),normal_objective=normal_obj,
            active_objective=active_obj,bridge_objective_uplift=bridge_uplift,
            runtime_seconds=time.perf_counter()-t0,
        ))
        print(f'{label} GW{gw}: score={score} cum={total} FH={use_fh_now} target={recommended_fh_gw}',flush=True)

    return dict(label=label,total_points=int(total),fh_gws=[int(x['gw']) for x in logs if x['fh_used']],
                transfers=int(sum(x['transfers'] for x in logs)),hit_points=int(sum(x['hit_cost'] for x in logs)),logs=logs)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--vfinal',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names,forecast=load_forecast(a.vfinal)

    baseline=run_track('baseline_ts_no_chips',gws,names,forecast,fh_aware=False,allow_fh=False)
    aware_off=run_track('fh_aware_chips_off',gws,names,forecast,fh_aware=True,allow_fh=False)

    b=pd.DataFrame(baseline['logs']);o=pd.DataFrame(aware_off['logs'])
    cols=['gw','score','transfers','hit_cost','bank','free_transfers_after']
    same=b[cols].reset_index(drop=True).equals(o[cols].reset_index(drop=True))
    if not same or baseline['total_points']!=aware_off['total_points']:
        diff=b[cols].merge(o[cols],on='gw',suffixes=('_base','_aware'))
        diff.to_csv(out/'baseline_regression_failure.csv',index=False)
        raise RuntimeError('FH-aware planner changes TS when chips are OFF')

    enabled=run_track('fh_aware_fh_on',gws,names,forecast,fh_aware=True,allow_fh=True)
    for r in (baseline,aware_off,enabled):
        pd.DataFrame(r.pop('logs')).to_csv(out/f"{r['label']}_gameweek_log.csv",index=False)

    summary={
      'classification':'full 2025/26 FH-aware TS bridge comparison on locked MM+vFinal chain',
      'weights':list(WEIGHTS),'hit_uncertainty_buffer':BUFFER,
      'first_half_fh_eligibility':[6,19],'second_half_fh_eligibility':[20,38],
      'baseline_no_chip':baseline,'fh_aware_chips_off':aware_off,'fh_aware_fh_on':enabled,
      'no_chip_regression_exact':True,
      'delta_fh_on_vs_baseline':int(enabled['total_points']-baseline['total_points']),
      'delta_transfers_vs_baseline':int(enabled['transfers']-baseline['transfers']),
      'delta_hits_vs_baseline':int(enabled['hit_points']-baseline['hit_points']),
    }
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
