#!/usr/bin/env python3
"""Oracle benchmark beside the PM+TS vFinal full-horizon proxy (GW22-38).

For every GW we report two hindsight ceilings:

1) reachable_oracle:
   Start from the model's exact pre-deadline state (squad, bank, purchase prices,
   FT). Give an oracle the actual GW points, allow the same 0..5 transfers,
   official -4 hits, normal budget/club/position constraints, and optimize
   transfers + XI + captain. No uncertainty buffer. This answers:
   "What was the best squad/strategy we could actually have ended with this GW
   from our state?"

2) unconstrained_oracle:
   Ignore the inherited squad/FT path and pick the best legal 15-man squad under
   the historical £100m budget for that GW, then best XI + captain using actual
   points. This is a theoretical weekly ceiling, not a reachable strategy.

The reachable oracle is the primary strategy-gap benchmark.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as base
from fpl_xpts.initial_squad_joint import InitialSquadConfig,optimize_initial_squad_joint
from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import (
    OwnedPlayer,ReplayState,actual_team_points,initial_squad,legalize_team_limit,valid_squad
)
from fpl_xpts.transfer_planner import execute_first_action
from fpl_xpts.transfer_planner_joint import JointPlannerConfig,plan_transfer_path_joint

MODEL=ROOT/'analysis/results/oracle_inputs/model'
BASE=ROOT/'analysis/results/oracle_inputs/base'
OUT=ROOT/'analysis/results/vfinal-oracle-gap-gw22-38-20261006-v1'


def ints(cell):
    if pd.isna(cell) or str(cell).strip()=='':
        return []
    return [int(float(x)) for x in str(cell).split(';') if str(x).strip() and str(x)!='nan']


def clone_state(s):
    return ReplayState(
        squad={pid:OwnedPlayer(pid,op.purchase_price) for pid,op in s.squad.items()},
        bank=int(s.bank),free_transfers=int(s.free_transfers)
    )


def reconstruct_gw22_state(gws,names,forecast):
    plans=pd.read_csv(BASE/'plans.csv')
    meta1=hp.gw_meta(gws,names,1)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    state=initial_squad(origin1,meta1,[1])
    for gw in range(1,22):
        q=plans[(plans.origin_gw==gw)&(plans.is_executed.astype(str).str.lower().isin(['true','1']))]
        if q.empty:continue
        r=q.iloc[0]
        meta=hp.gw_meta(gws,names,gw).drop_duplicates('id').set_index('id')
        for pid in ints(r.outgoing):state.squad.pop(pid)
        for pid in ints(r.incoming):state.squad[pid]=OwnedPlayer(pid,int(meta.loc[pid,'price_tenths']))
        state.bank=int(round(float(r.bank_after)*10))
        state.free_transfers=int(r.free_transfers_after)
    return state


def actual_projection(meta,actual,gw):
    a=actual[['id','points','minutes']].copy()
    a['gw']=gw
    a['xpts_mean']=a.points.astype(float)
    a['p_play']=(a.minutes.astype(float)>0).astype(float)
    out=meta[['id','web_name','team','position','price_tenths']].merge(a,on='id',how='left')
    out[['xpts_mean','p_play']]=out[['xpts_mean','p_play']].fillna(0.0)
    return out


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    gws,names,forecast=base.prepare()
    model_log=pd.read_csv(MODEL/'gameweek_log.csv')
    model_plans=pd.read_csv(MODEL/'plans.csv')
    state=reconstruct_gw22_state(gws,names,forecast)
    known=hp.gw_meta(gws,names,1)
    for seen in range(2,22):
        obs=hp.gw_meta(gws,names,seen)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')

    rows=[]
    for gw in range(22,39):
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        actual=hp.actual_gw(gws,gw)
        oracle_origin=actual_projection(meta,actual,gw)

        # Snapshot the exact state our model had before its real GW action.
        pre=clone_state(state)

        # Reachable hindsight oracle: actual points, same state, same 0..5 rules.
        oracle_state=clone_state(pre)
        ft_before=int(oracle_state.free_transfers)
        forced=legalize_team_limit(oracle_state,meta,oracle_origin,gw)
        oracle_state.free_transfers=max(0,ft_before-len(forced))
        ores=plan_transfer_path_joint(
            oracle_state,meta,oracle_origin,gw,
            JointPlannerConfig(
                weights=(1.0,),hit_uncertainty_buffer=0.0,max_transfers_per_week=5,
                first_gw_max_transfers=max(0,5-len(forced)),
                time_limit=60,mip_rel_gap=0.0,retry_time_limit=180,retry_mip_rel_gap=0.0
            )
        )
        optional=execute_first_action(oracle_state,ores,meta)
        ohit=sum(int(x.get('hit',0)) for x in forced)+sum(int(x.get('hit',0)) for x in optional)
        oplan=plan_squad(oracle_origin,list(oracle_state.squad),gw)
        reachable_score,_=actual_team_points(oplan,actual,None,ohit)

        # Unconstrained theoretical £100m weekly ceiling.
        init=optimize_initial_squad_joint(
            oracle_origin,meta,gw,
            InitialSquadConfig(weights=(1.0,),budget_tenths=1000,time_limit=60,mip_rel_gap=0.0)
        )
        unlimited_state=ReplayState(
            squad={pid:OwnedPlayer(pid,int(meta.set_index('id').loc[pid,'price_tenths'])) for pid in init.squad_ids},
            bank=int(init.bank_tenths),free_transfers=0
        )
        uplan=plan_squad(oracle_origin,init.squad_ids,gw)
        unconstrained_score,_=actual_team_points(uplan,actual,None,0)

        # Advance the model state using its executed action, so next pre-state is exact.
        q=model_plans[(model_plans.origin_gw==gw)&(model_plans.is_executed.astype(str).str.lower().isin(['true','1']))]
        if not q.empty:
            r=q.iloc[0]
            m=meta.drop_duplicates('id').set_index('id')
            for pid in ints(r.outgoing):state.squad.pop(pid)
            for pid in ints(r.incoming):state.squad[pid]=OwnedPlayer(pid,int(m.loc[pid,'price_tenths']))
            state.bank=int(round(float(r.bank_after)*10))
            state.free_transfers=int(r.free_transfers_after)

        mr=model_log[model_log.gw==gw].iloc[0]
        rows.append(dict(
            gw=gw,
            model_score=int(mr.score),
            reachable_oracle_score=int(reachable_score),
            reachable_gap=int(reachable_score-int(mr.score)),
            unconstrained_oracle_score=int(unconstrained_score),
            unconstrained_gap=int(unconstrained_score-int(mr.score)),
            oracle_transfers=int(len(forced)+len(optional)),
            oracle_hits=int(ohit),
            oracle_incoming=';'.join(map(str,ores.first_action.incoming if ores.first_action else ())),
            oracle_outgoing=';'.join(map(str,ores.first_action.outgoing if ores.first_action else ())),
            model_transfers=int(mr.transfers),
            model_hits=int(mr.hit_points),
            pre_ft=int(pre.free_transfers),
            pre_bank=float(pre.bank)/10.0,
        ))
        pd.DataFrame(rows).to_csv(OUT/'oracle_gap_by_gw.csv',index=False)
        print(
            f"GW{gw}: model={int(mr.score)} reachable_oracle={reachable_score} "
            f"gap={reachable_score-int(mr.score)} unconstrained={unconstrained_score}",
            flush=True
        )

    df=pd.DataFrame(rows)
    summary={
      'classification':'hindsight oracle benchmark beside vFinal full-horizon proxy',
      'model_points':int(df.model_score.sum()),
      'reachable_oracle_points':int(df.reachable_oracle_score.sum()),
      'reachable_oracle_gap':int(df.reachable_gap.sum()),
      'mean_reachable_gap_per_gw':float(df.reachable_gap.mean()),
      'median_reachable_gap_per_gw':float(df.reachable_gap.median()),
      'unconstrained_oracle_points':int(df.unconstrained_oracle_score.sum()),
      'unconstrained_oracle_gap':int(df.unconstrained_gap.sum()),
      'worst_strategy_gap_gws':df.nlargest(8,'reachable_gap')[['gw','model_score','reachable_oracle_score','reachable_gap']].to_dict(orient='records'),
      'note':'Reachable oracle uses actual outcomes and is a hindsight ceiling, not a deployable forecast strategy.'
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
