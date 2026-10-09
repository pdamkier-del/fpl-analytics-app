#!/usr/bin/env python3
"""GW6 counterfactual: exactly same TS state, three starter outages.

A 1-GW outage and a 6-GW outage are separate what-if shocks,
NOT claims about actual 2025/26 injuries.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from dataclasses import replace
import pandas as pd
import run_joint_fh_wc_stopping_replay as runner
import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as ts
from fpl_xpts.season_replay import initial_squad,legalize_team_limit
from fpl_xpts.transfer_planner import plan_transfer_path,execute_first_action
from fpl_xpts.wildcard_planner_v2 import build_asof_wc_projection
from fpl_xpts.wildcard_ts_action import compare_wc_as_ts_action
from fpl_xpts.joint_chip_stopping import ScenarioParameters,choose_joint_chip
from fpl_xpts.chip_planner import optimize_free_hit_squad
from fpl_xpts.optimize import plan_squad

def gw6_state(gws,names,forecast,cfg):
    meta1=hp.gw_meta(gws,names,1)
    initial=hp.complete_current_projection(forecast[forecast.origin_gw.eq(0)],meta1,1)
    state=initial_squad(initial,meta1,[1]);known=meta1.copy()
    for gw in range(1,6):
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin=ts.origin_with_meta(forecast,meta,gw)
        if gw>1:legalize_team_limit(state,meta,origin,gw)
        result=plan_transfer_path(state,meta,origin,gw,cfg)
        execute_first_action(state,result,meta)
    obs=hp.gw_meta(gws,names,6)
    known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
    meta=known.copy()
    origin=ts.origin_with_meta(forecast,meta,6)
    legalize_team_limit(state,meta,origin,6)
    return state,meta,origin

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--vfinal',required=True)
    ap.add_argument('--out',required=True);ap.add_argument('--structural')
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names,forecast=runner.load(a.vfinal);cfg=runner.cfg()
    state,meta,origin=gw6_state(gws,names,forecast,cfg)
    base=build_asof_wc_projection(forecast,meta,origin,6,cfg)
    lineup=plan_squad(base[base.gw.eq(6)],list(state.squad),6)
    active=lineup.rows[lineup.rows.role.isin(['C','VC','XI'])].copy()
    active=active.sort_values('xpts_mean',ascending=False)
    selected=active.id.astype(int).head(3).tolist()
    prior=origin[origin.gw.eq(6)].set_index('id')
    rows=[]
    structural=pd.read_csv(a.structural) if a.structural else pd.DataFrame()
    bg={int(x.gw):float(x.p_bgw) for x in structural.itertuples()}
    dg={int(x.gw):float(x.p_dgw) for x in structural.itertuples()}
    for scenario in ['healthy','three_out_one_gw','three_out_six_gws']:
        proxy=base.copy()
        if scenario!='healthy':
            mask=proxy.id.isin(selected)&(proxy.gw.eq(6) if scenario=='three_out_one_gw' else proxy.gw.between(6,11))
            proxy.loc[mask,'xpts_mean']=0.
            proxy.loc[mask,'p_play']=0.
        wc=compare_wc_as_ts_action(state,meta,proxy,6,cfg,max_candidates=2,milp_seconds=8.)
        bridge=plan_transfer_path(state,meta,proxy,6,replace(cfg,free_hit_gw=6))
        fh=optimize_free_hit_squad(state=state,meta=meta,forecast=proxy,gw=6,normal_score=0.)
        f_gain=float(bridge.objective+fh['fh_score']-wc.normal_objective)
        health=2 if scenario!='healthy' else 0
        decision=choose_joint_chip(
            gw=6,available_mask=3,g_fh_now=f_gain,g_wc_now=float(wc.gain),
            current_disruption=health,ft=state.free_transfers,
            bgw_by_gw=bg,dgw_by_gw=dg,params=ScenarioParameters(),draws=4500)
        rows.append(dict(scenario=scenario,chosen_players=';'.join(map(str,selected)),
                 names=';'.join(str(names.get(i,i)) for i in selected),
                 normal_ts_q=float(wc.normal_objective),gain_fh=f_gain,
                 gain_wc=float(wc.gain),q_save=float(decision.q_normal),
                 q_use_fh=float(decision.q_fh),q_use_wc=float(decision.q_wc),
                 action=decision.choice,wc_transfers=int(wc.transfers)))
    pd.DataFrame(rows).to_csv(out/'gw6_three_player_stress.csv',index=False)
    (out/'summary.json').write_text(json.dumps(rows,indent=2))
    print(pd.DataFrame(rows).to_string(index=False),flush=True)
if __name__=='__main__':main()
