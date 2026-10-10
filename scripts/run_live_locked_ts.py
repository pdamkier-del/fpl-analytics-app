#!/usr/bin/env python3
"""Strict live state bridge to the existing frozen TS v3; no synthetic manager."""
import argparse, json, sys
from dataclasses import asdict
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_xpts.season_replay import ReplayState,OwnedPlayer,valid_squad
from fpl_xpts.transfer_planner import plan_transfer_path,execute_first_action,clone_state
from fpl_xpts.optimize import plan_squad
from run_joint_fh_wc_stopping_replay import cfg
CHIPS={'wildcard','free_hit','bench_boost','triple_captain'}

def integer(x,name,lo,hi):
    if isinstance(x,bool) or not isinstance(x,int) or not lo<=x<=hi:raise ValueError('Invalid '+name)
    return x

def parse_state(raw,meta,gw,cutoff):
    if raw.get('season')!='2026-27' or raw.get('gw')!=gw:raise ValueError('Manager state season/GW mismatch')
    if not raw.get('source') or not raw.get('observed_at'):raise ValueError('Missing manager state provenance')
    observed=pd.Timestamp(raw['observed_at']);target=pd.Timestamp(cutoff)
    if observed.tzinfo is None or target.tzinfo is None or observed>target:raise ValueError('Manager state is after forecast cutoff')
    bank=integer(raw.get('bank_tenths'),'bank_tenths',0,1000)
    ft=integer(raw.get('free_transfers'),'free_transfers',1,5)
    owned={}
    for p in raw.get('squad',[]):
        pid=integer(p.get('id'),'player ID',1,1000000)
        price=integer(p.get('purchase_price_tenths'),'purchase price',1,1000)
        if pid in owned:raise ValueError('Duplicate owned player')
        owned[pid]=OwnedPlayer(pid,price)
    if not valid_squad(meta,owned):raise ValueError('Manager squad must have 15 legal players')
    used=raw.get('chips_used')
    if not isinstance(used,dict) or set(used)!=CHIPS:raise ValueError('All four chip histories are required')
    for chip,gws in used.items():
        if not isinstance(gws,list) or len(set(gws))!=len(gws):raise ValueError('Invalid chip history '+chip)
        for g in gws:integer(g,'chip GW',1,gw-1)
    return ReplayState(owned,bank,ft,used)

def project(payload):
    positions={1:'GKP',2:'DEF',3:'MID',4:'FWD'};meta=[];rows=[]
    first=min(payload['gws'])
    for p in payload['players']:
        meta.append({'id':p['id'],'web_name':p['name'],'position':positions[p['position']], 'team':p['team_id'],'price_tenths':p['price_tenths']})
        for w in p['weeks']:
            rows.append({'id':p['id'],'web_name':p['name'],'position':positions[p['position']],
                'gw':w['gw'],'origin_gw':first-1,'xpts_mean':w['xpts'],'p_play':w['p_play'],'fixtures':len(w['fixtures'])})
    return pd.DataFrame(meta),pd.DataFrame(rows)

def run(payload,raw,include_chips=False,tc_samples=None):
    meta,origin=project(payload);gw=min(payload['gws'])
    if sorted(payload['gws'])!=list(range(gw,gw+6)):raise ValueError('TS requires complete six-GW inputs')
    state=parse_state(raw,meta,gw,payload['data_asof'])
    diagnostic=not payload.get('locked_model_active',False) or any(payload.get('parts',{}).get(k)!='verified' for k in ('mm','pm_vfinal'))
    planned=plan_transfer_path(state,meta,origin,gw,cfg());after=clone_state(state)
    transfers=execute_first_action(after,planned,meta);lineup=plan_squad(origin,list(after.squad),gw)
    result={'locked_model_active':False,'ts_status':'diagnostic' if diagnostic else 'verified',
        'chips_status':'Not Available','ts_ran':True,'chips_ran':False,'forecast_cutoff':payload['data_asof'],
        'gw':gw,'manager_state_source':raw['source'],'plan':asdict(planned),'transfers':transfers,
        'lineup':json.loads(lineup.rows.to_json(orient='records')),
        'interpretation':'Hypothetical recommendations only. Only the first action would be executed; later actions require replanning. No FPL account is modified.',
        'blockers':list(payload.get('blockers',[]))}
    if include_chips:
        from fpl_xpts.wildcard_planner_v2 import build_asof_wc_projection
        from fpl_xpts.wildcard_ts_action import compare_wc_as_ts_action
        from fpl_xpts.chip_planner import optimize_free_hit_squad
        from fpl_xpts.bench_boost_policy import evaluate_bench_boost
        from fpl_xpts.final_chip_coordinator import choose_final_chip
        from fpl_xpts.tc_chip_bridge import tc_v2_opportunity,tc_candidate_eligible
        half_start,half_end=(1,19) if gw<=19 else (20,38)
        available={k:not any(half_start<=g<=half_end for g in raw['chips_used'][k]) for k in CHIPS}
        proxy=build_asof_wc_projection(origin,meta,origin,gw,cfg())
        wc=compare_wc_as_ts_action(state,meta,proxy,gw,cfg(),max_candidates=2,milp_seconds=8.) if available['wildcard'] else None
        fh=optimize_free_hit_squad(state=state,meta=meta,forecast=proxy,gw=gw,normal_score=0.) if available['free_hit'] else None
        bb=evaluate_bench_boost(lineup.rows) if available['bench_boost'] else None
        # Same locked SIMPLE_FH_WC branch used in the historical final replay.
        fh_gain=float(fh['fh_score'])-float(lineup.expected_score) if fh else 0.
        wc_gain=float(wc.gain) if wc else 0.;bb_gain=float(bb.incremental_xp) if bb else 0.
        tc=None;eligible=False
        if tc_samples is not None and available['triple_captain']:
            if set(map(int,tc_samples.gw.unique()))!=set(range(gw,half_end+1)):
                raise ValueError('TC needs complete current-half future-option scenarios; six GWs alone are insufficient')
            tc=tc_v2_opportunity(tc_samples,gw,eligible_current_ids=lineup.rows.loc[lineup.rows.role.isin(('C','VC','XI')),'id'])
            eligible=tc_candidate_eligible(tc,lineup.rows)
        choice=choose_final_chip(gw=gw,fh_available=available['free_hit'],wc_available=available['wildcard'],
            bb_available=available['bench_boost'],tc_available=tc is not None and available['triple_captain'],
            fh_gain=fh_gain,wc_gain=wc_gain,bb_gain=bb_gain,tc_action=tc['action'] if tc else 'SAVE_TC',
            tc_use_edge=tc.get('use_edge',float('-inf')) if tc else float('-inf'),tc_candidate_is_eligible=eligible)
        result.update(chips_ran=True,chips_status='diagnostic_partial' if tc is None and available['triple_captain'] else 'diagnostic',
            chip_assessment={'gw':gw,'provisional_choice_without_missing_tc':choice.chip,
                'fh_gain':fh_gain if fh else None,'wc_gain':wc_gain if wc else None,'bb_gain':bb_gain if bb else None,
                'q_fh':choice.q_fh if npfinite(choice.q_fh) else None,
                'q_wc':choice.q_wc if npfinite(choice.q_wc) else None,
                'q_bb':choice.q_bb if npfinite(choice.q_bb) else None,
                'availability':available,'tc':tc,'tc_status':'diagnostic_manual_confirmation_required' if tc else 'Not Available',
                'future_chip_gw':None,'future_chip_status':'Not Available: no complete cutoff-safe option ledger',
                'full_four_chip_decision_verified':False})
        if tc is None and available['triple_captain']:result['blockers'].append('TC requires verified scenarios through the current half and its original manual decision gate; no replacement option value is invented.')
    return result

def npfinite(x):
    import math
    return math.isfinite(x)

def main():
    p=argparse.ArgumentParser();p.add_argument('--forecast',type=Path,default=ROOT/'app/vfinal-diagnostic.json');p.add_argument('--state',type=Path);p.add_argument('--out',type=Path,default=ROOT/'work/live-final-model/live_ts_chip_audit.json');a=p.parse_args()
    # Diagnostic use was explicitly authorized; this never promotes the model.
    payload=json.loads(a.forecast.read_text());result={'locked_model_active':False,'ts_status':'Not Available','chips_status':'Not Available','ts_ran':False,'chips_ran':False}
    if not a.state or not a.state.exists():result['blockers']=['Missing verified manager squad, bank, FT, purchase prices and chip usage state.']
    else:
        result=run(payload,json.loads(a.state.read_text()),include_chips=True)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
