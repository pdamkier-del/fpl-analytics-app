#!/usr/bin/env python3
"""Full-season proxy replay for TS v4 joint rolling MILP.

Point model is locked. Chips are OFF.
Uses the recovered rolling Phase5Q archive solely as a full-season strategy proxy.

TS v4 mechanism:
- one joint MILP per deadline over visible 6GW horizon
- all players eligible
- 0–5 transfers per hypothetical GW
- exact bank / purchase-price / FT transitions
- XI + captain + vice optimized jointly by GW
- deterministic hit + uncertainty costs are NOT horizon-discounted
- only first action executed; replan next real GW

Forced club-limit repairs are accounted before the planner and consume FT/hit budget.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as base

from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import (
    OwnedPlayer, ReplayState, actual_team_points, initial_squad,
    legalize_team_limit, valid_squad
)
from fpl_xpts.transfer_planner import execute_first_action
from fpl_xpts.transfer_planner_joint import JointPlannerConfig, plan_transfer_path_joint
from run_v4rc_experiment import write_json, sha

OUT=ROOT/'analysis/results/transfer-strategy-v4-joint-replay-20261006-v1'
WEIGHTS=(1.00,.85,.70,.55,.40,.25)
BUFFER=1.5


def prepare():
    return base.prepare()


def origin_with_meta(forecast,meta,gw):
    return base.origin_with_meta(forecast,meta,gw)


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    gws,names,forecast=prepare()

    meta1=hp.gw_meta(gws,names,1)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    state=initial_squad(origin1,meta1,[1]); initial=list(state.squad)
    known=meta1.copy(); total=0; control=0; logs=[]; plans=[]

    checkpoint=OUT/'checkpoint.json'
    fingerprint={p:sha(ROOT/p) for p in [
        'src/fpl_xpts/transfer_planner_joint.py',
        'scripts/run_transfer_strategy_v4_joint_replay.py',
        'analysis/results/legacy-rolling-recovery-v1/manifest.json',
        'analysis/results/legacy-season-technical-replay-v1/runtime_input_manifest.json',
    ]}
    immutable_inputs=[
        'analysis/results/legacy-rolling-recovery-v1/manifest.json',
        'analysis/results/legacy-season-technical-replay-v1/runtime_input_manifest.json',
    ]

    next_gw=1
    if checkpoint.exists():
        saved=json.loads(checkpoint.read_text())
        if saved['fingerprint'] != fingerprint:
            allow_code_change=str(__import__('os').environ.get('ALLOW_CODE_CHANGE_RESUME','0'))=='1'
            inputs_ok=all(
                saved.get('fingerprint',{}).get(p)==fingerprint.get(p)
                for p in immutable_inputs
            )
            if not (allow_code_change and inputs_ok):
                raise RuntimeError('Checkpoint code/input mismatch; use a new output directory')
            print(
                f"Resuming checkpoint at GW{saved.get('next_gw')} across solver-only code change; "
                "immutable input hashes match.",
                flush=True,
            )
        state=ReplayState(
            {int(pid):OwnedPlayer(int(pid),int(price)) for pid,price in saved['purchases'].items()},
            int(saved['bank']), int(saved['free_transfers'])
        )
        initial=[int(x) for x in saved['initial']]
        total=int(saved['total']); control=int(saved['control'])
        logs=saved['logs']; plans=saved['plans']; next_gw=int(saved['next_gw'])
        for seen_gw in range(2,next_gw):
            obs=hp.gw_meta(gws,names,seen_gw)
            known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')

    for gw in range(next_gw,39):
        t0=time.perf_counter()
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin_raw=forecast[forecast.origin_gw==gw-1].copy()
        current=hp.complete_current_projection(origin_raw,meta,gw)
        origin=origin_with_meta(forecast,meta,gw)

        ft_before_all=int(state.free_transfers)
        forced=[]
        if gw>1:
            forced=legalize_team_limit(state,meta,origin,gw)
        forced_n=len(forced)
        forced_hit=sum(int(x.get('hit',0)) for x in forced)

        # Mandatory real-life club repairs consume transfers before the optional
        # optimizer. Remaining FT and current-GW transfer capacity are therefore
        # reduced exactly; future hypothetical GWs retain the normal 0–5 range.
        state.free_transfers=max(0,ft_before_all-forced_n)
        remaining_cap=max(0,5-forced_n)

        cfg=JointPlannerConfig(
            weights=WEIGHTS,
            hit_uncertainty_buffer=BUFFER,
            max_transfers_per_week=5,
            first_gw_max_transfers=remaining_cap,
            time_limit=60.0,
            mip_rel_gap=0.002,
            retry_time_limit=180.0,
            retry_mip_rel_gap=0.01,
        )
        result=plan_transfer_path_joint(state,meta,origin,gw,cfg)
        optional=execute_first_action(state,result,meta)
        optional_hit=sum(int(x.get('hit',0)) for x in optional)
        hit_cost=forced_hit+optional_hit

        if not valid_squad(meta,state.squad):
            raise RuntimeError(f'GW{gw}: invalid squad after TS v4 action')
        if state.bank < 0:
            raise RuntimeError(f'GW{gw}: negative bank')
        if not (0 <= state.free_transfers <= 5):
            raise RuntimeError(f'GW{gw}: invalid FT state {state.free_transfers}')
        if forced_n + len(optional) > 5:
            raise RuntimeError(f'GW{gw}: more than five total transfers')

        expected_hit=4*max(0,forced_n+len(optional)-ft_before_all)
        if hit_cost != expected_hit:
            raise RuntimeError(
                f'GW{gw}: hit mismatch recorded={hit_cost} expected={expected_hit} '
                f'FT={ft_before_all} transfers={forced_n+len(optional)}'
            )

        plan=plan_squad(current,list(state.squad),gw)
        score,_=actual_team_points(plan.rows,hp.actual_gw(gws,gw),None,hit_cost)
        total+=score

        cp=plan_squad(current,initial,gw)
        control_score,_=actual_team_points(cp.rows,hp.actual_gw(gws,gw),None,0)
        control+=control_score

        elapsed=time.perf_counter()-t0
        action=result.first_action
        logs.append(dict(
            gw=gw, score=int(score), cumulative=int(total),
            transfers=int(forced_n+len(optional)), forced_transfers=int(forced_n),
            optional_transfers=int(len(optional)), hit_cost=int(hit_cost),
            bank=float(state.bank)/10.0, free_transfers_after=int(state.free_transfers),
            free_transfers_before=int(ft_before_all),
            planner_objective=float(result.objective),
            runtime_seconds=float(elapsed),
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

        saved=dict(
            fingerprint=fingerprint,next_gw=gw+1,
            purchases={str(pid):int(op.purchase_price) for pid,op in state.squad.items()},
            bank=int(state.bank),free_transfers=int(state.free_transfers),
            initial=initial,total=int(total),control=int(control),logs=logs,plans=plans,
        )
        tmp=checkpoint.with_suffix('.tmp'); write_json(tmp,saved); tmp.replace(checkpoint)
        pd.DataFrame(logs).to_csv(OUT/'gameweek_log.csv',index=False)
        pd.DataFrame(plans).to_csv(OUT/'plans.csv',index=False)
        print(
            f'GW{gw}: score={score} cum={total} transfers={forced_n+len(optional)} '
            f'hits={hit_cost} FT={state.free_transfers} runtime={elapsed:.1f}s',
            flush=True,
        )

    summary=dict(
        classification='TS v4 joint rolling MILP full-season strategy proxy; chips OFF; point model locked',
        forecast_provider='recovered rolling Phase5Q archive',
        configuration=dict(
            weights=list(WEIGHTS),hit_buffer=BUFFER,max_transfers_per_week=5,
            solver_time_limit_seconds=60.0,mip_rel_gap=0.002,
            retry_time_limit_seconds=180.0,retry_mip_rel_gap=0.01,
            candidate_generator='NONE - joint MILP over full player universe',
            horizon='rolling/receding 6GW; execute first action only',
            deterministic_transfer_costs_horizon_discounted=False,
        ),
        total_points=int(total),
        transfers=int(sum(x['transfers'] for x in logs)),
        forced_transfers=int(sum(x['forced_transfers'] for x in logs)),
        hit_points=int(sum(x['hit_cost'] for x in logs)),
        no_transfer_control=int(control),
        uplift=int(total-control),
        points_gw1_21=int(sum(x['score'] for x in logs if x['gw']<=21)),
        points_gw22_38=int(sum(x['score'] for x in logs if x['gw']>=22)),
        runtime_seconds=float(sum(x['runtime_seconds'] for x in logs)),
        reference=dict(ts_v3=1992,best_valid_ts_v3_tuning=2030,ts_v2=2137),
        caveat='Strategy proxy only; recovered Phase5Q rolling forecasts, not cutoff-safe rolling vFinal.',
    )
    write_json(OUT/'summary.json',summary)
    write_json(OUT/'manifest.json',dict(
        sources=[
            dict(path='scripts/run_transfer_strategy_v4_joint_replay.py',sha256=sha(Path(__file__))),
            dict(path='src/fpl_xpts/transfer_planner_joint.py',sha256=sha(ROOT/'src/fpl_xpts/transfer_planner_joint.py')),
        ],
        outputs=[dict(path=p.name,sha256=sha(p)) for p in sorted(OUT.iterdir()) if p.name!='manifest.json'],
    ))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    run()
