#!/usr/bin/env python3
"""Full-season proxy replay for rolling Transfer Strategy v3.

Point model remains locked. Chips are OFF.

Uses recovered rolling Phase5Q full-season forecasts as the only available
cutoff-safe full-season strategy proxy. This is not the final vFinal season
performance replay, but it is a true TS v3 season replay with receding-horizon
planning, FT state and buffer 1.5.

Primary configuration:
- 6GW weights (1.00,0.85,0.70,0.55,0.40,0.25)
- hit uncertainty buffer 1.5
- beam width 30
- 2 MILP candidates per transfer count
- max 5 transfers per hypothetical GW
- chips OFF

Comparator included:
- TS v2 lineup-aware static-horizon policy with same 6GW weights and buffer 1.5
"""
from __future__ import annotations
import json,sys,time
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_horizon_policy_comparison as hp
import run_transfer_strategy_v2_grid as tsv2

from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import (
    actual_team_points, initial_squad, legalize_team_limit, valid_squad
)
from fpl_xpts.transfer_planner import (
    PlannerConfig, execute_first_action, plan_transfer_path
)
from run_v4rc_experiment import write_json,sha

OUT=ROOT/'analysis/results/transfer-strategy-v3-replay-20261005-v1'
WEIGHTS=(1.00,.85,.70,.55,.40,.25)
BUFFER=1.5


def prepare():
    gws=hp.unpack_runtime('merged_gw.csv')
    raw=hp.unpack_runtime('players_raw.csv')
    names=raw.set_index('id').web_name.astype(str).to_dict()
    forecast=hp.rolling_forecast()[['id','web_name','position','gw','origin_gw','xpts_mean','p_play','fixtures']].copy()
    forecast.id=forecast.id.astype(int)
    return gws,names,forecast


def origin_with_meta(forecast,meta,gw):
    origin=forecast[forecast.origin_gw==gw-1].copy()
    mm=meta[['id','team','price_tenths']].rename(columns={'team':'meta_team','price_tenths':'meta_price_tenths'})
    origin=origin.merge(mm,on='id',how='left')
    if 'team' not in origin: origin['team']=origin.meta_team
    else: origin['team']=origin.team.fillna(origin.meta_team)
    origin['price_tenths']=origin.meta_price_tenths
    return origin


def run_v3(gws,names,forecast):
    meta1=hp.gw_meta(gws,names,1)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    state=initial_squad(origin1,meta1,[1]);initial=list(state.squad)
    known=meta1.copy();total=0;control=0;logs=[];plans=[]
    config=PlannerConfig(weights=WEIGHTS,hit_uncertainty_buffer=BUFFER,beam_width=30,
                         candidates_per_transfer_count=2,max_transfers_per_week=5,
                         milp_time_limit=12.0)
    for gw in range(1,39):
        t0=time.time()
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin=origin_with_meta(forecast,meta,gw)
        current=hp.complete_current_projection(origin,meta,gw)

        forced=[]
        if gw>1:
            forced=legalize_team_limit(state,meta,origin,gw)

        # If forced real-life club transfers were needed, legalize_team_limit has
        # already mutated state. Planner starts from that legal state.
        result=plan_transfer_path(state,meta,origin,gw,config)
        transfers=execute_first_action(state,result,meta)
        hit_cost=sum(int(x.get('hit',0)) for x in transfers) + sum(int(x.get('hit',0)) for x in forced)

        if not valid_squad(meta,state.squad):
            raise RuntimeError(f'GW{gw}: invalid squad after TS v3 action')

        plan=plan_squad(current,list(state.squad),gw)
        score,_=actual_team_points(plan.rows,hp.actual_gw(gws,gw),None,hit_cost)
        total+=score

        cp=plan_squad(current,initial,gw)
        control_score,_=actual_team_points(cp.rows,hp.actual_gw(gws,gw),None,0)
        control+=control_score

        action=result.first_action
        logs.append(dict(
            gw=gw,score=score,cumulative=total,
            transfers=len(transfers)+len(forced),forced_transfers=len(forced),
            hit_cost=hit_cost,bank=state.bank/10,free_transfers_after=state.free_transfers,
            planner_objective=result.objective,
            runtime_seconds=time.time()-t0,
        ))
        for step,a in enumerate(result.path,1):
            plans.append(dict(
                origin_gw=gw,step=step,target_gw=a.gw,transfers=a.transfers,
                outgoing=';'.join(map(str,a.outgoing)),incoming=';'.join(map(str,a.incoming)),
                official_hit_points=a.official_hit_points,
                uncertainty_penalty=a.uncertainty_penalty,
                projected_manager_score=a.projected_manager_score,
                utility_this_gw=a.utility_this_gw,
                free_transfers_before=a.free_transfers_before,
                free_transfers_after=a.free_transfers_after,
                bank_before=a.bank_before/10,bank_after=a.bank_after/10,
                is_executed=(step==1),
            ))
        print(f'GW{gw}: {score} pts, cum {total}, transfers {len(transfers)+len(forced)}, FT {state.free_transfers}',flush=True)
    return dict(
        total_points=int(total),
        transfers=int(sum(x['transfers'] for x in logs)),
        hit_points=int(sum(x['hit_cost'] for x in logs)),
        no_transfer_control=int(control),
        uplift=int(total-control),
        logs=logs,plans=plans,
    )


def run_v2(gws,names,forecast):
    r=tsv2.run_policy('tsv2_6gw_buffer_1.5',WEIGHTS,BUFFER,gws,forecast,names)
    return r


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    gws,names,forecast=prepare()

    v3=run_v3(gws,names,forecast)
    pd.DataFrame(v3.pop('logs')).to_csv(OUT/'tsv3_gameweek_log.csv',index=False)
    pd.DataFrame(v3.pop('plans')).to_csv(OUT/'tsv3_plans.csv',index=False)

    v2=run_v2(gws,names,forecast)
    pd.DataFrame(v2.pop('logs')).to_csv(OUT/'tsv2_gameweek_log.csv',index=False)

    comparison=pd.DataFrame([
        dict(strategy='TS v2 static 6GW',total_points=v2['total_points'],transfers=v2['transfers'],
             hit_points=v2['hit_points'],uplift=v2['uplift']),
        dict(strategy='TS v3 rolling 6GW',total_points=v3['total_points'],transfers=v3['transfers'],
             hit_points=v3['hit_points'],uplift=v3['uplift']),
    ])
    comparison.to_csv(OUT/'comparison.csv',index=False)

    summary=dict(
      classification='TS v3 full-season strategy proxy; chips off; point model locked',
      forecast_provider='recovered rolling Phase5Q archive',
      configuration=dict(weights=list(WEIGHTS),hit_buffer=BUFFER,beam_width=30,
                         candidates_per_transfer_count=2,max_transfers_per_week=5),
      ts_v3=v3,ts_v2_comparator=v2,
      delta_vs_v2=dict(
          total_points=int(v3['total_points']-v2['total_points']),
          transfers=int(v3['transfers']-v2['transfers']),
          hit_points=int(v3['hit_points']-v2['hit_points']),
          uplift=int(v3['uplift']-v2['uplift']),
      ),
      caveat='Not the final vFinal season score; forecast provider remains recovered Phase5Q until cutoff-safe rolling vFinal forecasts are generated.'
    )
    write_json(OUT/'summary.json',summary)
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(
      sources=[
        dict(path='scripts/run_transfer_strategy_v3_replay.py',sha256=sha(Path(__file__))),
        dict(path='src/fpl_xpts/transfer_planner.py',sha256=sha(ROOT/'src/fpl_xpts/transfer_planner.py')),
      ],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]
    ))
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
