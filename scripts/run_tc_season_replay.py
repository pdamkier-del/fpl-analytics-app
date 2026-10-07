#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))

from fpl_xpts.chip_planner import ChipPlannerConfig,decide_tc_from_samples
import run_horizon_policy_comparison as hp

def actual_table():
    gws=hp.unpack_runtime('merged_gw.csv')
    raw=hp.unpack_runtime('players_raw.csv').drop_duplicates('id')
    names=raw.set_index('id').web_name.astype(str).to_dict()
    actual=gws.groupby(['GW','element'],as_index=False).agg(
        actual_points=('total_points','sum'),actual_minutes=('minutes','sum')
    )
    actual['name']=actual.element.map(names).fillna(actual.element.astype(str))

    # Optional fixture context if preserved in merged runtime input.
    extras=[]
    if 'was_home' in gws.columns:
        home=gws.groupby(['GW','element']).was_home.first().rename('was_home')
        extras.append(home)
    if 'opponent_team' in gws.columns:
        opp=gws.groupby(['GW','element']).opponent_team.first().rename('opponent_team')
        extras.append(opp)
    if 'team' in gws.columns:
        team=gws.groupby(['GW','element']).team.first().rename('team')
        extras.append(team)
    for s in extras:
        actual=actual.merge(s.reset_index(),on=['GW','element'],how='left')
    return actual,names,gws

def load_origin(root,gw):
    candidates=[
        root/f'tc-origin-{gw}'/'tc_samples.csv.gz',
        root/f'origin-{gw}'/'tc_samples.csv.gz',
        root/f'tc-{gw}'/'tc_samples.csv.gz',
    ]
    for p in candidates:
        if p.exists(): return pd.read_csv(p)
    # actions/download-artifact with pattern usually creates artifact-name dirs.
    hits=list(root.glob(f'**/*{gw}*/tc_samples.csv.gz'))
    if len(hits)==1:return pd.read_csv(hits[0])
    if not hits:raise FileNotFoundError(f'No TC samples found for GW{gw} under {root}')
    raise RuntimeError(f'Ambiguous TC samples for GW{gw}: {hits}')

def replay_half(root,start,end,discount):
    config=ChipPlannerConfig(future_discount=discount,top_tc_candidates=20)
    trace=[];decision=None
    for gw in range(start,end+1):
        samples=load_origin(root,gw)
        res=decide_tc_from_samples(
            samples,current_gw=gw,period_end_gw=end,config=config
        )
        probs=res['timing_probabilities'].copy()
        future=probs[probs.gw>gw].sort_values('probability_best',ascending=False)
        best_future=future.iloc[0] if len(future) else None

        cur=samples[samples.gw.eq(gw)].groupby(
            ['candidate_id','candidate_name'],as_index=False
        ).points.mean().sort_values('points',ascending=False).iloc[0]

        trace.append(dict(
            half=f'{start}-{end}',gw=gw,action=res['action'],
            current_candidate_id=int(cur.candidate_id),
            current_candidate_name=str(cur.candidate_name),
            current_candidate_xp=float(cur.points),
            probability_current_gw_best=float(res['probability_current_gw_best']),
            use_now_value=float(res['use_now_value']),
            save_option_value=float(res['save_option_value']),
            use_edge=float(res['use_edge']),
            most_likely_future_gw=(int(best_future.gw) if best_future is not None else None),
            most_likely_future_probability=(float(best_future.probability_best) if best_future is not None else None),
        ))
        if res['action']=='USE_TC':
            decision=dict(
                half=f'{start}-{end}',decision_gw=gw,
                player_id=int(res['candidate_id']),
                player_name=str(res['candidate_name']),
                predicted_tc_marginal=float(res['use_now_value']),
                save_option_value=float(res['save_option_value']),
                use_edge=float(res['use_edge']),
                probability_gw_best=float(res['probability_current_gw_best']),
            )
            break
    if decision is None: raise RuntimeError(f'No TC decision made in {start}-{end}')
    return decision,pd.DataFrame(trace)

def hindsight(actual,start,end):
    z=actual[actual.GW.between(start,end)].copy()
    return z.sort_values(['actual_points','GW'],ascending=[False,True]).reset_index(drop=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--origins',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--discount',type=float,default=.97)
    a=ap.parse_args()
    root=Path(a.origins);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    actual,names,gws=actual_table()

    # Locked vFinal begins GW6. First chip is therefore decision-tested GW6-19.
    d1,t1=replay_half(root,6,19,a.discount)
    d2,t2=replay_half(root,20,38,a.discount)
    decisions=pd.DataFrame([d1,d2])

    decisions=decisions.merge(
        actual[['GW','element','actual_points','actual_minutes']],
        left_on=['decision_gw','player_id'],right_on=['GW','element'],how='left'
    ).drop(columns=['GW','element'])
    decisions['actual_tc_added_points']=decisions.actual_points

    h1=hindsight(actual,1,19)
    h2=hindsight(actual,20,38)
    top=pd.concat([
        h1.head(20).assign(half='1-19'),
        h2.head(20).assign(half='20-38')
    ],ignore_index=True)

    # Audit the most obvious elite-captain heuristic explicitly.
    haaland=actual[actual.name.astype(str).str.contains('Haaland',case=False,na=False)].copy()
    haaland=haaland.sort_values('GW')

    decisions.to_csv(out/'tc_decisions.csv',index=False)
    pd.concat([t1,t2],ignore_index=True).to_csv(out/'tc_decision_trace.csv',index=False)
    top.to_csv(out/'tc_hindsight_top20_each_half.csv',index=False)
    haaland.to_csv(out/'haaland_actual_gws.csv',index=False)

    best1=h1.iloc[0];best2=h2.iloc[0]
    summary=dict(
        classification='TC-only full-season decision replay with locked vFinal from GW6',
        future_discount=float(a.discount),
        tc_chips=2,
        first_half_live_decision_window=[6,19],
        second_half_live_decision_window=[20,38],
        first_half_cold_start_caveat='GW1-5 excluded from live TC stopping rule; included in hindsight audit',
        decisions=decisions.to_dict('records'),
        hindsight_best=[
            dict(half='1-19',gw=int(best1.GW),player_id=int(best1.element),player_name=str(best1['name']),actual_points=int(best1.actual_points)),
            dict(half='20-38',gw=int(best2.GW),player_id=int(best2.element),player_name=str(best2['name']),actual_points=int(best2.actual_points)),
        ],
        actual_tc_added_points=int(decisions.actual_tc_added_points.fillna(0).sum()),
        hindsight_max_added_points=int(best1.actual_points+best2.actual_points),
        hindsight_gap=int(best1.actual_points+best2.actual_points-decisions.actual_tc_added_points.fillna(0).sum()),
    )
    (out/'summary.json').write_text(json.dumps(summary,indent=2,default=str)+'\n')
    print(json.dumps(summary,indent=2,default=str))

if __name__=='__main__':
    main()
