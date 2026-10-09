#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from dataclasses import replace
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import run_transfer_strategy_v3_replay as ts
import run_horizon_policy_comparison as hp
from fpl_xpts.chip_planner import optimize_free_hit_squad
from fpl_xpts.fh_transfer_planner import _state_before_target
from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import actual_team_points,initial_squad,legalize_team_limit,valid_squad
from fpl_xpts.transfer_planner import PlannerConfig,plan_transfer_path,execute_first_action,clone_state,_apply_selected_squad

WEIGHTS=(1.0,.60,.36,.216,.1296,.07776)
BUFFER=1.0

EXPECTED_BEST_REMAINING={
    1:21.475,2:21.475,3:21.475,4:21.475,5:19.750,6:17.850,7:17.725,8:17.325,
    9:13.350,10:13.350,11:13.350,12:13.350,13:13.350,14:13.350,15:13.350,
    16:10.050,17:9.425,18:9.425,19:0.0,
    20:18.825,21:18.825,22:18.825,23:18.825,24:18.025,25:18.025,26:17.375,
    27:16.050,28:12.700,29:10.150,30:10.150,31:8.850,32:8.850,33:7.300,
    34:4.625,35:2.000,36:1.475,37:0.0,38:0.0,
}

def cfg():
    return PlannerConfig(weights=WEIGHTS,hit_uncertainty_buffer=BUFFER,beam_width=20,
        candidates_per_transfer_count=1,candidate_limit_per_position=18,
        top_targets_per_position=18,local_bundle_beam=60,candidate_return_per_depth=12,
        max_transfers_per_week=5,candidate_backend='fast_local',milp_time_limit=2.0)

def load(vfinal):
    gws,names,cold=ts.prepare()
    cold=cold[cold.origin_gw<=4].copy()
    vf=pd.read_csv(vfinal)
    vf['web_name']=vf.id.astype(int).map(names).fillna(vf.id.astype(str))
    keep=['id','web_name','position','gw','origin_gw','xpts_mean','p_play','fixtures']
    vf=vf[keep].copy();vf.id=vf.id.astype(int)
    return gws,names,pd.concat([cold[keep],vf],ignore_index=True)


from fpl_xpts.wildcard_planner_v2 import build_asof_wc_projection
from fpl_xpts.wildcard_ts_action import compare_wc_as_ts_action
from fpl_xpts.joint_chip_stopping import ScenarioParameters,choose_joint_chip,FH,WC
from fpl_xpts.simple_chip_thresholds import choose_simple_chip
from fpl_xpts.bench_boost_policy import evaluate_bench_boost, bb_threshold

def _current_health(state,meta,origin,forecast,gw):
    """Observed at deadline: important owned players newly unavailable."""
    ids=set(state.squad)
    current=origin[origin.gw.eq(gw)].drop_duplicates('id').set_index('id')
    hist=forecast[(forecast.origin_gw<gw-1)&
                  (forecast.origin_gw>=gw-6)&
                  (forecast.gw==forecast.origin_gw+1)]
    recent=hist.groupby('id').xpts_mean.median()
    adverse=[]
    for pid in ids:
        if pid not in current.index:continue
        now=current.loc[pid]
        xp=float(now.xpts_mean)
        prob=float(now.p_play)
        usual=float(recent.get(pid,xp))
        if usual>=3.0 and (prob<.35 or (xp<.15*usual and float(now.fixtures)>0)):
            adverse.append(pid)
    return (2 if len(adverse)>=3 else 1 if adverse else 0),adverse

def run(label,gws,names,forecast,use_chips=False,params=ScenarioParameters(),
        structural=None,seed=20261009,simple_thresholds=None,start_gw=1,bb_lambda=None):
    meta1=hp.gw_meta(gws,names,start_gw)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==start_gw-1],meta1,start_gw)
    state=initial_squad(origin1,meta1,[start_gw])
    known=meta1.copy();total=0;logs=[];pcfg=cfg()
    used={'FH':set(),'WC':set(),'BB':set()}
    for gw in range(start_gw,39):
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin_raw=forecast[forecast.origin_gw==gw-1].copy()
        current=hp.complete_current_projection(origin_raw,meta,gw)
        origin=ts.origin_with_meta(forecast,meta,gw)
        forced=legalize_team_limit(state,meta,origin,gw) if gw>start_gw else []
        pre_bank=state.bank;pre_ft=state.free_transfers;pre_ids=set(state.squad)
        half=1 if gw<=19 else 2
        mask=(FH if half not in used['FH'] else 0)|(WC if half not in used['WC'] else 0)
        health,unavailable=_current_health(state,meta,origin,forecast,gw)
        decision=None;fh=None;wc=None;chip='normal'
        bb_gain=None;bb_q=None;bb_bench_ids=[];normal_bb_path=None
        # Screening is a COMPUTE budget, not a rule saying other GWs can never
        # use chips. Check all deadlines where severe lineup disruption is seen,
        # plus a dense set of ordinary candidate weeks and half expiration.
        checkpoints={5,6,8,10,12,14,16,18,19,20,22,24,26,28,30,32,34,36,38}
        assess=bool(use_chips and (mask or (bb_lambda is not None and half not in used['BB'])) and (simple_thresholds is not None or gw in checkpoints or health>=2))
        if assess:
            proxy=build_asof_wc_projection(forecast,meta,origin,gw,pcfg)
            wc_cmp=compare_wc_as_ts_action(state,meta,proxy,gw,pcfg,
                                            max_candidates=2,milp_seconds=8.) if mask&WC else None
            normal_proxy=(wc_cmp.normal_result if wc_cmp else
                          plan_transfer_path(state,meta,proxy,gw,pcfg))
            if mask&FH:
                bridge=plan_transfer_path(state,meta,proxy,gw,replace(pcfg,free_hit_gw=gw))
                fh_candidate=optimize_free_hit_squad(
                    state=state,meta=meta,forecast=proxy,gw=gw,normal_score=0.)
                fh_gain=bridge.objective+fh_candidate['fh_score']-normal_proxy.objective
                if simple_thresholds is not None:
                    normal_state=clone_state(state)
                    execute_first_action(normal_state,normal_proxy,meta)
                    normal_week_score=plan_squad(current,list(normal_state.squad),gw).expected_score
                    fh_gain=float(fh_candidate['fh_score'])-float(normal_week_score)
            else:
                bridge=None;fh_candidate=None;fh_gain=-1.e6
            wc_gain=float(wc_cmp.gain) if wc_cmp else -1.e6
            decision=choose_joint_chip(
                gw=gw,available_mask=mask,g_fh_now=float(fh_gain),
                g_wc_now=wc_gain,current_disruption=health,ft=state.free_transfers,
                params=params,draws=2500,seed=seed,
                bgw_by_gw=({int(x.gw):float(x.p_bgw) for x in structural.itertuples()} if structural is not None else None),
                dgw_by_gw=({int(x.gw):float(x.p_dgw) for x in structural.itertuples()} if structural is not None else None)) if simple_thresholds is None else choose_simple_chip(gw,mask,fh_gain,wc_gain,*simple_thresholds)
            if bb_lambda is not None and half not in used['BB']:
                # FH/WC decision values are untouched. BB uses the normal *locked*
                # TS transfer path and its actual deadline lineup, not the WC proxy.
                normal_bb_path=plan_transfer_path(state,meta,origin,gw,pcfg)
                bb_state=clone_state(state)
                execute_first_action(bb_state,normal_bb_path,meta)
                bb_plan=plan_squad(current,list(bb_state.squad),gw)
                bb_est=evaluate_bench_boost(bb_plan.rows)
                bb_gain=float(bb_est.incremental_xp)
                bb_bench_ids=list(bb_est.bench_player_ids)
                bb_q=bb_gain-bb_threshold(gw,float(bb_lambda))
                best_other=max(0.,float(decision.q_fh),float(decision.q_wc))
                if bb_q>best_other+1e-9:
                    chip='bb'
                    used['BB'].add(half)
                    state.chips_used['bench_boost'].append(gw)
                    moves=execute_first_action(state,normal_bb_path,meta)
                    hit=sum(int(x.get('hit',0)) for x in moves)+sum(int(x.get('hit',0)) for x in forced)
                    transfers=len(moves)+len(forced)
            if chip=='normal' and decision.choice=='wc':
                chip='wc';wc=wc_cmp;state=wc.state;used['WC'].add(half)
                if state.free_transfers!=pre_ft:raise AssertionError('WC FT changed')
                hit=0;transfers=wc.transfers
            elif chip=='normal' and decision.choice=='fh':
                chip='fh';fh=fh_candidate;used['FH'].add(half)
                moves=execute_first_action(state,bridge,meta)
                if moves:raise AssertionError('FH permanently transferred')
                if set(state.squad)!=pre_ids or state.bank!=pre_bank or state.free_transfers!=pre_ft:
                    raise AssertionError('FH state not restored')
                hit=0;transfers=0
        if chip=='normal':
            normal=normal_bb_path if normal_bb_path is not None else plan_transfer_path(state,meta,origin,gw,pcfg)
            moves=execute_first_action(state,normal,meta)
            hit=sum(int(x.get('hit',0)) for x in moves)+sum(int(x.get('hit',0)) for x in forced)
            transfers=len(moves)+len(forced)
        if not valid_squad(meta,state.squad):
            raise AssertionError(f'GW{gw}: invalid team')
        if chip=='fh':
            score,_=actual_team_points(fh['plan_rows'],hp.actual_gw(gws,gw),'free_hit',0)
        else:
            lineup=plan_squad(current,list(state.squad),gw)
            score,_=actual_team_points(lineup.rows,hp.actual_gw(gws,gw),('bench_boost' if chip=='bb' else None),hit)
        total+=int(score)
        logs.append(dict(gw=gw,score=int(score),cumulative=int(total),
                         chip=chip,assessed=assess,health=health,
                         currently_unavailable=';'.join(map(str,unavailable)),
                         g_fh_now=(decision.g_fh_now if decision else None),
                         g_wc_now=(decision.g_wc_now if decision else None),
                         q_normal=(decision.q_normal if decision else None),
                         q_fh=(decision.q_fh if decision else None),
                         q_wc=(decision.q_wc if decision else None),
                         bb_gain=bb_gain,bb_q=bb_q,
                         bb_bench_ids=';'.join(map(str,bb_bench_ids)),
                         bb_bench_names=';'.join(names.get(i,str(i)) for i in bb_bench_ids),
                         ft=int(state.free_transfers),bank=int(state.bank),
                         transfers=int(transfers),hit_cost=int(hit)))
        print(label,'GW',gw,'points',score,'cum',total,'chip',chip,
              'health',health,'gains',
              ((round(decision.g_fh_now,2),round(decision.g_wc_now,2)) if decision else None),
              flush=True)
    return dict(label=label,total_points=total,
                fh_gws=[x['gw'] for x in logs if x['chip']=='fh'],
                wc_gws=[x['gw'] for x in logs if x['chip']=='wc'],
                bb_gws=[x['gw'] for x in logs if x['chip']=='bb'],
                transfers=sum(x['transfers'] for x in logs),
                hit_points=sum(x['hit_cost'] for x in logs),logs=logs)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--vfinal',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--structural')
    ap.add_argument('--calibration',required=True)
    ap.add_argument('--persistent-fraction',type=float,default=.35)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names,forecast=load(a.vfinal)
    struct=pd.read_csv(a.structural) if a.structural else None
    baseline=run('locked_baseline',gws,names,forecast)
    pd.DataFrame(baseline.pop('logs')).to_csv(out/'baseline.csv',index=False)
    if baseline['total_points']!=2125:raise AssertionError('Locked TS baseline changed')
    results={'baseline':baseline}
    historical=json.loads(Path(a.calibration).read_text())
    params=ScenarioParameters(new_mild=float(historical['p_one_or_two_unexpected_zero']),
        new_severe=float(historical['p_three_plus_unexpected_zero']),
        mild_persistence=float(historical['p_zero_minutes_persists_one_gw']),
        severe_persistence=float(historical['p_zero_minutes_persists_one_gw']),
        persistent_shock_fraction=a.persistent_fraction)
    record=run('joint_stopping',gws,names,forecast,True,params,struct)
    pd.DataFrame(record.pop('logs')).to_csv(out/'joint_stopping.csv',index=False)
    results['joint_stopping']=record
    results['risk_params']=dict(vars(params))
    results['calibration_source']='2022-23 to 2024-25 regular GW conditional minute-unavailability proxy'
    # Fast and deterministic policy-only sensitivity analysis at GW6.
    # It varies future shocks, not the current observed 2025/26 result.
    sensitivity=[]
    from fpl_xpts.joint_chip_stopping import choose_joint_chip
    for severe in (.015,.053,.12,.20):
        p=replace(params,new_severe=severe)
        for gain_wc in (5.,10.,15.,20.):
            d=choose_joint_chip(gw=6,available_mask=3,g_fh_now=12.,
                 g_wc_now=gain_wc,current_disruption=0,ft=2,
                 params=p,draws=5000)
            sensitivity.append(dict(severe_rate=severe,g_wc=gain_wc,
                                    choice=d.choice,q_normal=d.q_normal,
                                    q_fh=d.q_fh,q_wc=d.q_wc))
    pd.DataFrame(sensitivity).to_csv(out/'gw6_disaster_sensitivity.csv',index=False)
    (out/'summary.json').write_text(json.dumps(results,indent=2))
    print('FINAL_SUMMARY',json.dumps(results,indent=2),flush=True)
if __name__=='__main__':main()
