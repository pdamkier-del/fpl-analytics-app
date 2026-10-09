#!/usr/bin/env python3
"""Six-GW counterfactual: identical pre-WC roster, normal TS vs WC then TS."""
import argparse, json
from pathlib import Path
from collections import defaultdict
import pandas as pd
import run_joint_fh_wc_stopping_replay as base
from fpl_xpts.optimize import plan_squad
from fpl_xpts.transfer_planner import plan_transfer_path, execute_first_action, clone_state
from fpl_xpts.season_replay import actual_team_points, legalize_team_limit, valid_squad

def player_breakdown(plan, actual):
    truth=actual.set_index('id')
    role=plan.set_index('id')
    active=plan[plan.role.isin(['C','VC','XI'])].id.astype(int).tolist()
    score,subs=actual_team_points(plan,actual,None,0)
    for pid in active[:]:
        if pid not in truth.index or int(truth.loc[pid,'minutes'])==0:
            active.remove(pid)
    active.extend(pid for pid in subs if pid not in active)
    cap=int(plan.loc[plan.role=='C','id'].iloc[0])
    vice=int(plan.loc[plan.role=='VC','id'].iloc[0])
    captain=cap if cap in truth.index and int(truth.loc[cap,'minutes'])>0 else (vice if vice in truth.index and int(truth.loc[vice,'minutes'])>0 else None)
    actual_p={}
    for pid in active:
        actual_p[pid]=actual_p.get(pid,0)+int(truth.loc[pid,'points'])
    if captain is not None:
        actual_p[captain]=actual_p.get(captain,0)+int(truth.loc[captain,'points'])
    starter=plan[plan.role.isin(['C','VC','XI'])]
    xp={int(x.id):float(x.xpts_mean) for x in starter.itertuples()}
    cr=role.loc[cap];vr=role.loc[vice]
    xp[cap]+=float(cr.xpts_mean)
    xp[vice]+=(1.0-float(cr.p_play))*float(vr.xpts_mean)
    return xp,actual_p,score

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--vfinal',required=True);ap.add_argument('--out',required=True)
    args=ap.parse_args()
    gws,names,forecast=base.load(args.vfinal)
    saved={}
    original=base.compare_wc_as_ts_action
    def capture(state,meta,origin,gw,config,**kw):
        result=original(state,meta,origin,gw,config,**kw)
        if gw in (6,26):
            saved[gw]=(clone_state(state),meta.copy(),result)
        return result
    base.compare_wc_as_ts_action=capture
    history=base.run('chip_history',gws,names,forecast,use_chips=True,simple_thresholds=(10,20))
    assert history['total_points']==2209
    assert history['wc_gws']==[6,26]
    pcfg=base.cfg()
    rows=[]; week_rows=[]; moves=[]
    for start in (6,26):
        initial,initial_meta,wc_candidate=saved[start]
        for variant in ('normal_ts','wc_then_ts'):
            state=clone_state(initial if variant=='normal_ts' else wc_candidate.state)
            known=initial_meta.copy()
            for gw in range(start,start+6):
                if gw>start:
                    obs=base.hp.gw_meta(gws,names,gw)
                    known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
                meta=known.copy()
                origin=base.ts.origin_with_meta(forecast,meta,gw)
                current=base.hp.complete_current_projection(forecast[forecast.origin_gw==gw-1].copy(),meta,gw)
                hit=0
                before=set(state.squad)
                if gw>start:
                    forced=legalize_team_limit(state,meta,origin,gw)
                    hit+=sum(int(z.get('hit',0)) for z in forced)
                if variant=='normal_ts' or gw>start:
                    planned=plan_transfer_path(state,meta,origin,gw,pcfg)
                    executed=execute_first_action(state,planned,meta)
                    hit+=sum(int(z.get('hit',0)) for z in executed)
                after=set(state.squad)
                assert valid_squad(meta,state.squad)
                moves.append(dict(start=start,variant=variant,gw=gw,chip=('wc' if variant=='wc_then_ts' and gw==start else 'normal'),out=';'.join(names.get(i,str(i)) for i in sorted(before-after)),incoming=';'.join(names.get(i,str(i)) for i in sorted(after-before)),hit=hit,bank=state.bank,ft=state.free_transfers))
                plan=plan_squad(current,list(state.squad),gw)
                xp,actuals,score=player_breakdown(plan,base.hp.actual_gw(gws,gw))
                assert score==sum(actuals.values())
                assert abs(sum(xp.values())-plan.expected_score)<1e-6
                expected=float(plan.expected_score)
                week_rows.append(dict(start=start,variant=variant,gw=gw,expected_points=expected,actual_points=score-hit,hit=hit,raw_actual=score))
                for pid in set(xp)|set(actuals):
                    rows.append(dict(start=start,variant=variant,gw=gw,id=pid,name=names.get(pid,str(pid)),xp=float(xp.get(pid,0)),actual=int(actuals.get(pid,0)),in_starting_squad=pid in after))
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(out/'players_by_gw.csv',index=False)
    pd.DataFrame(week_rows).to_csv(out/'gameweek_comparison.csv',index=False)
    pd.DataFrame(moves).to_csv(out/'transfers.csv',index=False)
    totals=pd.DataFrame(week_rows).groupby(['start','variant'],as_index=False)[['expected_points','actual_points','hit']].sum()
    players=pd.DataFrame(rows).groupby(['start','variant','id','name'],as_index=False)[['xp','actual']].sum()
    players.to_csv(out/'players_six_gw.csv',index=False)
    summary=dict(chip_gws=history['wc_gws'],totals=totals.to_dict('records'),transfers=moves)
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print('SIX_GW_WC_TS_AUDIT',json.dumps(summary),flush=True)

if __name__=='__main__':main()
