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
from fpl_xpts.fh_transfer_planner import _state_before_target, evaluate_fh_aware_path
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

def raw_fh_values(state,meta,origin,gw,period_end,pcfg):
    normal=plan_transfer_path(state,meta,origin,gw,replace(pcfg,free_hit_gw=None))
    vals=[]
    for target in [int(x) for x in normal.horizon_gws if int(x)<=int(period_end)]:
        before=_state_before_target(state,normal,meta,target)
        # Compare FH with the normal TS squad AFTER this GW's permanent action.
        # Previously it used before.squad, overstating the marginal FH gain.
        action=next((a for a in normal.path if int(a.gw)==target),None)
        if action is None:
            normal_ids=list(before.squad)
        else:
            selected=(set(before.squad)-set(action.outgoing))|set(action.incoming)
            after,_,_=_apply_selected_squad(before,selected,meta)
            normal_ids=list(after.squad)
        fh=optimize_free_hit_squad(state=before,meta=meta,forecast=origin,gw=target,
                                   normal_squad_ids=normal_ids)
        vals.append(dict(gw=target,gain=float(fh['fh_gain']),fh=fh))
    return normal,vals

import numpy as np
def mc_stopping_value(gw,historical,structure,draws=2048):
    """Expected stopping value: decisions have no clairvoyant future information."""
    end=19 if gw<=19 else 38
    if gw>=end:return 0.
    raw=historical[historical.half.eq(1 if gw<=19 else 2)]
    raw=raw[np.isfinite(raw.fh_gap)]
    normal=raw.loc[raw.kind.eq('SGW'),'fh_gap'].to_numpy(float)
    if not len(normal):normal=raw.fh_gap.to_numpy(float)
    if not len(normal):raise RuntimeError('Missing historical FH gaps')
    pools={}
    for kind in ['SGW','BGW','DGW']:
        sample=raw.loc[raw.kind.eq(kind),'fh_gap'].to_numpy(float)
        pools[kind]=sample if len(sample)>=3 else np.concatenate([sample,normal,normal])
    rng=np.random.default_rng(1729+gw)
    v=0.
    for target in range(end,gw,-1):
        z=structure[structure.gw.eq(target)]
        pb=float(z.iloc[0].p_bgw) if len(z) else 0.
        pdg=float(z.iloc[0].p_dgw) if len(z) else 0.
        pb=max(0.,min(1.,pb));pdg=max(0.,min(1.-pb,pdg))
        category=rng.choice(3,size=draws,p=[1-pb-pdg,pb,pdg])
        gains=np.empty(draws)
        for i,key in enumerate(['SGW','BGW','DGW']):
            mask=category==i
            gains[mask]=rng.choice(pools[key],size=int(mask.sum()))
        v=float(np.mean(np.maximum(gains,v)))
    return v

def run(label,gws,names,forecast,use_fh,ref,structural_threshold,historical,structure,first_fh_min_gw=1):
    meta1=hp.gw_meta(gws,names,1)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    state=initial_squad(origin1,meta1,[1])
    known=meta1.copy();total=0;logs=[];used=set();pcfg=cfg()
    for gw in range(1,39):
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin_raw=forecast[forecast.origin_gw==gw-1].copy()
        current=hp.complete_current_projection(origin_raw,meta,gw)
        origin=ts.origin_with_meta(forecast,meta,gw)
        forced=[]
        if gw>1:
            forced=legalize_team_limit(state,meta,origin,gw)
        half=1 if gw<=19 else 2
        period_end=19 if half==1 else 38
        normal=plan_transfer_path(state,meta,origin,gw,pcfg)
        now_candidate=plan_transfer_path(state,meta,origin,gw,replace(pcfg,free_hit_gw=gw))
        fh_projection=optimize_free_hit_squad(state=state,meta=meta,forecast=origin,gw=gw,normal_score=0.)
        q_fh_now=float(now_candidate.objective+fh_projection['fh_score'])
        now_gain=q_fh_now-float(normal.objective)
        future_option=mc_stopping_value(gw,historical,structure)
        q_save=float(normal.objective)+future_option
        potential_best=future_option
        threshold=future_option
        structural_save=future_option
        best_future=None
        future_gain=0.
        available=bool(use_fh and half not in used and (half!=1 or gw>=first_fh_min_gw))
        fire=bool(available and (gw==period_end or q_fh_now>q_save))
        # Same-deadline, same-state no-chip counterfactual. This isolates the
        # chip's actual gain from differences between whole-season TS histories.
        counterfactual_actual=None
        counterfactual_xp=None
        counterfactual_ids=None
        pre_fh_bank=state.bank
        pre_fh_ft=state.free_transfers
        pre_fh_squad=set(state.squad)
        if fire:
            normal_state=clone_state(state)
            normal_moves=execute_first_action(normal_state,normal,meta)
            normal_hit=sum(int(x.get('hit',0)) for x in normal_moves)
            normal_plan=plan_squad(current,list(normal_state.squad),gw)
            counterfactual_actual,_=actual_team_points(normal_plan.rows,hp.actual_gw(gws,gw),None,normal_hit)
            counterfactual_xp=float(normal_plan.expected_score)
            counterfactual_ids=list(normal_state.squad)
            result=now_candidate
        else:
            result=normal
        transfers=execute_first_action(state,result,meta)
        hit=sum(int(x.get('hit',0)) for x in transfers)+sum(int(x.get('hit',0)) for x in forced)
        if not valid_squad(meta,state.squad):
            raise RuntimeError(f'invalid squad GW{gw}')
        if fire:
            fh=optimize_free_hit_squad(state=state,meta=meta,forecast=origin,gw=gw,normal_squad_ids=list(state.squad))
            score,_=actual_team_points(fh['plan_rows'],hp.actual_gw(gws,gw),'free_hit',0)
            used.add(half)
            if set(state.squad)!=pre_fh_squad or state.bank!=pre_fh_bank or state.free_transfers!=pre_fh_ft:
                raise AssertionError(f'FH bridge mutated permanent squad/bank/FT at GW{gw}')
        else:
            plan=plan_squad(current,list(state.squad),gw)
            score,_=actual_team_points(plan.rows,hp.actual_gw(gws,gw),None,hit)
        total+=int(score)
        logs.append(dict(gw=gw,score=int(score),cumulative=total,fh_used=fire,fh_gain_now=now_gain,
                         best_visible_future_gain=future_gain,best_visible_future_gw=(None if best_future is None else best_future.gw),
                         expected_best_remaining_gain=potential_best,structural_save_value=structural_save,fh_use_threshold=threshold,
                         q_fh_now=q_fh_now,q_save=q_save,q_normal=float(normal.objective),
                         transfers=len(transfers)+len(forced),hit_cost=hit,
                         normal_same_state_actual=counterfactual_actual,
                         normal_same_state_xp=counterfactual_xp,
                         fh_same_state_actual_gain=(int(score)-int(counterfactual_actual) if fire else None),
                         fh_same_state_xp_gain=(float(fh['fh_score'])-float(counterfactual_xp) if fire else None),
                         fh_fixture_double_count=(int(sum(origin[(origin.gw==gw)&(origin.fixtures==2)].id.isin(fh['fh_squad_ids']))) if fire else None),
                         forecast_origin_gw=gw-1))
        print(f'{label} GW{gw}: {score} cum={total} FH={fire} now={now_gain:.3f} future={future_gain:.3f} prior={potential_best:.3f} structural={structural_save:.3f}',flush=True)
    return dict(label=label,total_points=total,fh_gws=[x['gw'] for x in logs if x['fh_used']],
                transfers=sum(x['transfers'] for x in logs),hit_points=sum(x['hit_cost'] for x in logs),logs=logs)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--vfinal',required=True);ap.add_argument('--out',required=True);ap.add_argument('--reference',required=True);ap.add_argument('--structural-prior',required=True);ap.add_argument('--historical',required=True);ap.add_argument('--structure',required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names,forecast=load(a.vfinal)
    ref=pd.read_csv(a.reference).set_index('gw')['expected_best_remaining_gap'].to_dict()
    sp=pd.read_csv(a.structural_prior).set_index('gw')
    structural_threshold={int(g):float(r['base_expected_best_remaining_gap']+r['latent_structural_bonus']) for g,r in sp.iterrows()}
    historical=pd.read_csv(a.historical)
    structure=pd.read_csv(a.structure)
    b=run('baseline',gws,names,forecast,False,ref,structural_threshold,historical,structure)
    f=run('fh_v3_mc',gws,names,forecast,True,ref,structural_threshold,historical,structure)
    delayed7=run('fh_v3_no_gw6',gws,names,forecast,True,ref,structural_threshold,historical,structure,first_fh_min_gw=7)
    delayed10=run('fh_v3_wait_until_gw10',gws,names,forecast,True,ref,structural_threshold,historical,structure,first_fh_min_gw=10)
    pd.DataFrame(b.pop('logs')).to_csv(out/'baseline.csv',index=False)
    pd.DataFrame(f.pop('logs')).to_csv(out/'fh_v3_mc.csv',index=False)
    pd.DataFrame(delayed7.pop('logs')).to_csv(out/'fh_v3_no_gw6.csv',index=False)
    pd.DataFrame(delayed10.pop('logs')).to_csv(out/'fh_v3_wait_until_gw10.csv',index=False)
    if b['total_points']!=2125:
        raise RuntimeError(f"baseline {b['total_points']} != 2125")
    s={'classification':'FH v3 Monte Carlo optimal stopping pilot',
       'rule':'use FH if bridge Q now exceeds normal TS Q plus max(known future FH bridge advantage, empirical best unknown future FH gap); no additive structural uplift',
       'historical_reference':'2024/25 exact FH gaps with historical BGW/DGW event likelihood; stochastic stopping proxy',
       'baseline':b,'fh':f,'delta':f['total_points']-b['total_points'],'no_gw6':delayed7,'wait_until_gw10':delayed10}
    (out/'summary.json').write_text(json.dumps(s,indent=2)+'\n')
    print(json.dumps(s,indent=2))
if __name__=='__main__':
    main()
