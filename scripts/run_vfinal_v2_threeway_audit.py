#!/usr/bin/env python3
"""Three-way GW22-38 audit for coverage-fixed vFinal proxy v2.

For each GW:
- forecast: model's projected manager score at the executed first action
- actual: realized manager score
- best reachable: hindsight oracle from the exact same pre-deadline state,
  with the same 0..5 transfer rules, budget, FT and official hit costs.

The hindsight oracle knows actual outcomes and is diagnostic only.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as base
from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import OwnedPlayer,ReplayState,actual_team_points,initial_squad,legalize_team_limit
from fpl_xpts.transfer_planner import execute_first_action
from fpl_xpts.transfer_planner_joint import JointPlannerConfig,plan_transfer_path_joint

MODEL=ROOT/'analysis/results/threeway_inputs/model'
BASE=ROOT/'analysis/results/threeway_inputs/base'
OUT=ROOT/'analysis/results/vfinal-v2-threeway-audit-20261006-v1'

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
        r=q.iloc[0];meta=hp.gw_meta(gws,names,gw).drop_duplicates('id').set_index('id')
        for pid in ints(r.outgoing):state.squad.pop(pid)
        for pid in ints(r.incoming):state.squad[pid]=OwnedPlayer(pid,int(meta.loc[pid,'price_tenths']))
        state.bank=int(round(float(r.bank_after)*10));state.free_transfers=int(r.free_transfers_after)
    return state

def actual_projection(meta,actual,gw):
    a=actual[['id','points','minutes']].copy()
    a['xpts_mean']=a.points.astype(float);a['p_play']=(a.minutes.astype(float)>0).astype(float)
    out=meta[['id','web_name','team','position','price_tenths']].merge(a[['id','xpts_mean','p_play']],on='id',how='left')
    out['gw']=int(gw);out[['xpts_mean','p_play']]=out[['xpts_mean','p_play']].fillna(0.0)
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
        meta=known.copy();actual=hp.actual_gw(gws,gw);oracle_origin=actual_projection(meta,actual,gw)

        pre=clone_state(state)
        oracle_state=clone_state(pre)
        ft_before=int(oracle_state.free_transfers)
        forced=legalize_team_limit(oracle_state,meta,oracle_origin,gw)
        oracle_state.free_transfers=max(0,ft_before-len(forced))
        ores=plan_transfer_path_joint(
            oracle_state,meta,oracle_origin,gw,
            JointPlannerConfig(weights=(1.0,),hit_uncertainty_buffer=0.0,max_transfers_per_week=5,
                first_gw_max_transfers=max(0,5-len(forced)),
                time_limit=60,mip_rel_gap=0.0,retry_time_limit=180,retry_mip_rel_gap=0.0))
        optional=execute_first_action(oracle_state,ores,meta)
        ohit=sum(int(x.get('hit',0)) for x in forced)+sum(int(x.get('hit',0)) for x in optional)
        oplan=plan_squad(oracle_origin,list(oracle_state.squad),gw)
        best,_=actual_team_points(oplan.rows,actual,None,ohit)

        q=model_plans[(model_plans.origin_gw==gw)&(model_plans.is_executed.astype(str).str.lower().isin(['true','1']))]
        forecast_score=float('nan')
        model_out='';model_in=''
        if not q.empty:
            r=q.iloc[0]
            forecast_score=float(r.projected_manager_score)
            model_out=str(r.outgoing);model_in=str(r.incoming)
            mm=meta.drop_duplicates('id').set_index('id')
            for pid in ints(r.outgoing):state.squad.pop(pid)
            for pid in ints(r.incoming):state.squad[pid]=OwnedPlayer(pid,int(mm.loc[pid,'price_tenths']))
            state.bank=int(round(float(r.bank_after)*10));state.free_transfers=int(r.free_transfers_after)

        mr=model_log[model_log.gw==gw].iloc[0]
        rows.append(dict(
            gw=gw,
            forecast_points=forecast_score,
            actual_points=int(mr.score),
            best_reachable_points=int(best),
            actual_minus_forecast=float(mr.score)-forecast_score,
            best_minus_actual=int(best-int(mr.score)),
            best_minus_forecast=float(best)-forecast_score,
            model_transfers=int(mr.transfers),model_hits=int(mr.hit_points),
            oracle_transfers=int(len(forced)+len(optional)),oracle_hits=int(ohit),
            model_outgoing=model_out,model_incoming=model_in,
            oracle_outgoing=';'.join(map(str,ores.first_action.outgoing if ores.first_action else ())),
            oracle_incoming=';'.join(map(str,ores.first_action.incoming if ores.first_action else ())),
        ))
        pd.DataFrame(rows).to_csv(OUT/'threeway_by_gw.csv',index=False)
        print(f"GW{gw}: forecast={forecast_score:.1f} actual={int(mr.score)} best={best}",flush=True)

    df=pd.DataFrame(rows)
    summary={
      'gameweeks':int(len(df)),
      'forecast_total':float(df.forecast_points.sum()),
      'actual_total':int(df.actual_points.sum()),
      'best_reachable_total':int(df.best_reachable_points.sum()),
      'mean_forecast':float(df.forecast_points.mean()),
      'mean_actual':float(df.actual_points.mean()),
      'mean_best_reachable':float(df.best_reachable_points.mean()),
      'forecast_bias_actual_minus_forecast':float((df.actual_points-df.forecast_points).mean()),
      'forecast_mae':float((df.actual_points-df.forecast_points).abs().mean()),
      'strategy_gap_total':int((df.best_reachable_points-df.actual_points).sum()),
      'mean_strategy_gap':float((df.best_reachable_points-df.actual_points).mean()),
      'warning':'Best reachable is a hindsight oracle with actual outcomes, not a deployable forecast strategy.'
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
