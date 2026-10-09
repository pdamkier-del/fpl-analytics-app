#!/usr/bin/env python3
"""Fit Bench Boost timing on frozen FH/WC replay; TS and chips remain intact."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import run_joint_fh_wc_stopping_replay as replay
from fpl_xpts.bench_boost_policy import evaluate_bench_boost,bb_threshold
from fpl_xpts.season_replay import actual_team_points

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--vfinal',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--grid',default='0,4,8,12,16,20,25,30,40')
    ap.add_argument('--reserved-tc-gws',default='',help='Comma-separated locked TC weeks to exclude')
    a=ap.parse_args()
    reserved=set(map(int,filter(None,a.reserved_tc_gws.split(','))))
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names,forecast=replay.load(a.vfinal)
    records={}
    original=replay.plan_squad
    def record_plan(projections,squad_ids,gw):
        plan=original(projections,squad_ids,gw)
        estimate=evaluate_bench_boost(plan.rows)
        actual=replay.hp.actual_gw(gws,gw)
        score_none,_=actual_team_points(plan.rows,actual,None,0)
        score_bb,_=actual_team_points(plan.rows,actual,'bench_boost',0)
        records[int(gw)]=dict(gw=int(gw),bench_xp=estimate.bench_xp,
            normal_autosub_xp=estimate.expected_autosub_xp,
            bb_increment_xp=estimate.incremental_xp,
            bb_actual_extra=int(score_bb-score_none),
            bench_players=';'.join(names.get(i,str(i)) for i in estimate.bench_player_ids))
        return plan
    replay.plan_squad=record_plan
    result=replay.run('frozen_fh_wc',gws,names,forecast,
                      use_chips=True,simple_thresholds=(10.0,20.0))
    assert result['total_points']==2209,'Frozen FH/WC points drift'
    fixed_chips={r['gw']:r['chip'] for r in result['logs']}
    candidates=[]
    for gw,rec in sorted(records.items()):
        if fixed_chips.get(gw)!='normal' or gw in reserved:continue
        candidates.append(rec)
    pd.DataFrame(candidates).to_csv(out/'bb_weekly_opportunities.csv',index=False)
    grid=[float(x) for x in a.grid.split(',')]
    fit=[]
    for threshold in grid:
        selected=[]
        for first,last in ((1,19),(20,38)):
            for r in candidates:
                gw=r['gw']
                if first<=gw<=last and r['bb_increment_xp']>bb_threshold(gw,threshold):
                    selected.append(r);break
        delta=sum(r['bb_actual_extra'] for r in selected)
        fit.append(dict(lambda_bb=threshold,total_points=2209+delta,
            bb_gws=[r['gw'] for r in selected],
            expected_bb_gain=[round(r['bb_increment_xp'],3) for r in selected],
            actual_bb_gain=[r['bb_actual_extra'] for r in selected]))
    fit.sort(key=lambda r:(-r['total_points'],r['lambda_bb']))
    pd.DataFrame(fit).to_csv(out/'bb_threshold_grid.csv',index=False)
    summary=dict(frozen_fh_wc_points=2209,fh_gws=result['fh_gws'],
                 wc_gws=result['wc_gws'],reserved_tc_gws=sorted(reserved),
                 best_in_sample=fit[0],grid=fit,
                 caveat='BB does not alter transfers; TC weeks excluded only if supplied; 2025/26 is in-sample')
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print('BB_GRID_FINAL',json.dumps(summary),flush=True)

if __name__=='__main__':main()
