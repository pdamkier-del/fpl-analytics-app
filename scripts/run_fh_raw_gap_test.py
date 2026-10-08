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
from fpl_xpts.transfer_planner import PlannerConfig,plan_transfer_path,execute_first_action

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
        fh=optimize_free_hit_squad(state=before,meta=meta,forecast=origin,gw=target,
                                   normal_squad_ids=list(before.squad))
        vals.append(dict(gw=target,gain=float(fh['fh_gain']),fh=fh))
    return normal,vals

def run(label,gws,names,forecast,use_fh):
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
        normal,vals=raw_fh_values(state,meta,origin,gw,period_end,pcfg)
        now=next((x for x in vals if x['gw']==gw),None)
        future=[x for x in vals if x['gw']>gw]
        best_future=max(future,key=lambda x:x['gain']) if future else None
        now_gain=-1e9 if now is None else now['gain']
        future_gain=0.0 if best_future is None else best_future['gain']
        potential_best=float(EXPECTED_BEST_REMAINING[gw])
        threshold=max(future_gain,potential_best)
        available=bool(use_fh and half not in used)
        fire=bool(available and (gw==period_end or now_gain>=threshold))
        if fire:
            result=plan_transfer_path(state,meta,origin,gw,replace(pcfg,free_hit_gw=gw))
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
        else:
            plan=plan_squad(current,list(state.squad),gw)
            score,_=actual_team_points(plan.rows,hp.actual_gw(gws,gw),None,hit)
        total+=int(score)
        logs.append(dict(gw=gw,score=int(score),cumulative=total,fh_used=fire,fh_gain_now=now_gain,
                         best_visible_future_gain=future_gain,best_visible_future_gw=(None if best_future is None else best_future['gw']),
                         expected_best_remaining_gain=potential_best,fh_use_threshold=threshold,
                         transfers=len(transfers)+len(forced),hit_cost=hit))
        print(f'{label} GW{gw}: {score} cum={total} FH={fire} now={now_gain:.3f} future={future_gain:.3f} prior={potential_best:.3f}',flush=True)
    return dict(label=label,total_points=total,fh_gws=[x['gw'] for x in logs if x['fh_used']],
                transfers=sum(x['transfers'] for x in logs),hit_points=sum(x['hit_cost'] for x in logs),logs=logs)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--vfinal',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names,forecast=load(a.vfinal)
    b=run('baseline',gws,names,forecast,False)
    f=run('fh_raw_gap',gws,names,forecast,True)
    pd.DataFrame(b.pop('logs')).to_csv(out/'baseline.csv',index=False)
    pd.DataFrame(f.pop('logs')).to_csv(out/'fh_raw_gap.csv',index=False)
    if b['total_points']!=2125:
        raise RuntimeError(f"baseline {b['total_points']} != 2125")
    s={'classification':'raw FH xP-gap timing test',
       'rule':'use FH when current raw xP gain >= max(best raw visible future xP gain, historical mean best remaining FH gap to GW19/38); no FH discount/decay',
       'historical_reference':'mean of each seasons best later FH proxy from 2022/23-2025/26',
       'baseline':b,'fh':f,'delta':f['total_points']-b['total_points']}
    (out/'summary.json').write_text(json.dumps(s,indent=2)+'\n')
    print(json.dumps(s,indent=2))
if __name__=='__main__':
    main()
