#!/usr/bin/env python3
"""Audit TS v4 GW18 using the completed replay artifact.

This is diagnostic only: reconstructs the executed GW18 state, lineup/captain,
forecast xP and actual points. It does not alter or rerun the season.
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
from fpl_xpts.season_replay import actual_team_points

ART=ROOT/'analysis/results/transfer-strategy-v4-joint-replay-20261006-v1'


def ints(cell):
    if pd.isna(cell) or str(cell).strip()=='':
        return []
    return [int(float(x)) for x in str(cell).split(';') if x and x!='nan']


def main():
    cp=json.loads((ART/'checkpoint.json').read_text())
    plans=pd.read_csv(ART/'plans.csv')
    logs=pd.read_csv(ART/'gameweek_log.csv')

    gws,names,forecast=base.prepare()
    squad=set(map(int,cp['initial']))
    purchase={}  # not needed for lineup audit

    executed=[]
    for gw in range(1,19):
        q=plans[(plans.origin_gw==gw)&(plans.is_executed==True)]
        if q.empty:
            continue
        r=q.iloc[0]
        outs=ints(r.outgoing); ins=ints(r.incoming)
        for x in outs: squad.remove(x)
        for x in ins: squad.add(x)
        executed.append((gw,outs,ins,float(r.projected_manager_score)))

    meta=hp.gw_meta(gws,names,18)
    origin_raw=forecast[forecast.origin_gw==17].copy()
    current=hp.complete_current_projection(origin_raw,meta,18)
    actual=hp.actual_gw(gws,18)
    plan=plan_squad(current,list(squad),18)
    total,autosubs=actual_team_points(plan.rows,actual,None,0)

    table=plan.rows[['id','web_name','position','role','xpts_mean','p_play']].copy()
    table=table.merge(actual,on='id',how='left')
    table[['points','minutes']]=table[['points','minutes']].fillna(0)
    table['id']=table.id.astype(int)
    table['points']=table.points.astype(int)
    table['minutes']=table.minutes.astype(int)
    table['autosub_in']=table.id.isin(autosubs)

    # Transfer detail and direct same-player counterfactual.
    gw18=plans[(plans.origin_gw==18)&(plans.is_executed==True)].iloc[0]
    out_id=ints(gw18.outgoing)[0] if ints(gw18.outgoing) else None
    in_id=ints(gw18.incoming)[0] if ints(gw18.incoming) else None
    bymeta=meta.set_index('id')
    act=actual.set_index('id')
    cur=current.set_index('id')

    transfer={
        'out_id':out_id,'out':names.get(out_id,str(out_id)) if out_id else None,
        'in_id':in_id,'in':names.get(in_id,str(in_id)) if in_id else None,
        'out_xp':float(cur.xpts_mean.get(out_id,0.0)) if out_id else None,
        'in_xp':float(cur.xpts_mean.get(in_id,0.0)) if in_id else None,
        'out_actual':int(act.points.get(out_id,0)) if out_id else None,
        'in_actual':int(act.points.get(in_id,0)) if in_id else None,
    }

    captain=table[table.role=='C'].iloc[0]
    vice=table[table.role=='VC'].iloc[0]
    log=logs[logs.gw==18].iloc[0].to_dict()

    # Counterfactual: undo only the GW18 transfer, then re-optimize GW18 XI/captain
    # using the SAME deadline forecast. This isolates the immediate transfer effect.
    cf_squad=set(squad)
    if out_id is not None and in_id is not None:
        cf_squad.remove(in_id); cf_squad.add(out_id)
        cfplan=plan_squad(current,list(cf_squad),18)
        cfscore,cfautosubs=actual_team_points(cfplan.rows,actual,None,0)
        cf_expected=float(cfplan.expected_score)
    else:
        cfscore=total; cf_expected=float(plan.expected_score)

    payload={
        'gw':18,
        'replay_score':int(total),
        'logged_score':int(log['score']),
        'projected_manager_score':float(gw18.projected_manager_score),
        'plan_expected_score':float(plan.expected_score),
        'transfer':transfer,
        'captain':{
            'id':int(captain.id),'name':str(captain.web_name),
            'xpts':float(captain.xpts_mean),'actual':int(captain.points),'minutes':int(captain.minutes),
        },
        'vice':{
            'id':int(vice.id),'name':str(vice.web_name),
            'xpts':float(vice.xpts_mean),'actual':int(vice.points),'minutes':int(vice.minutes),
        },
        'autosubs':list(map(int,autosubs)),
        'counterfactual_undo_gw18_transfer':{
            'expected_score':cf_expected,'actual_score':int(cfscore),
            'actual_delta_vs_executed':int(cfscore-total),
        },
        'squad_rows':table.to_dict(orient='records'),
        'executed_history':executed,
    }
    print(json.dumps(payload,indent=2,default=str))
    table.to_csv(ART/'gw18_lineup_audit.csv',index=False)
    (ART/'gw18_audit.json').write_text(json.dumps(payload,indent=2,default=str))


if __name__=='__main__':
    main()
