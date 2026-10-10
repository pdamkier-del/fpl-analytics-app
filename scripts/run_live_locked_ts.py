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

def main():
    p=argparse.ArgumentParser();p.add_argument('--forecast',type=Path,default=ROOT/'app/vfinal-diagnostic.json');p.add_argument('--state',type=Path);p.add_argument('--out',type=Path,default=ROOT/'work/live-final-model/live_ts_chip_audit.json');a=p.parse_args()
    payload=json.loads(a.forecast.read_text());result={'locked_model_active':False,'ts_status':'Not Available','chips_status':'Not Available','ts_ran':False,'chips_ran':False}
    if not a.state or not a.state.exists():result['blockers']=['Missing verified manager squad, bank, FT, purchase prices and chip usage state.']
    elif any(payload.get('parts',{}).get(k)!='verified' for k in ('mm','pm_vfinal')):
        # Diagnostic PM outputs must not silently drive a certified recommendation.
        meta,origin=project(payload);parse_state(json.loads(a.state.read_text()),meta,min(payload['gws']),payload['data_asof'])
        result['blockers']=['Model source-quality release gate is not verified.','Locked TC future-option scenarios are unavailable.']
    else:
        meta,origin=project(payload);gw=min(payload['gws'])
        state=parse_state(json.loads(a.state.read_text()),meta,gw,payload['data_asof'])
        planned=plan_transfer_path(state,meta,origin,gw,cfg());after=clone_state(state)
        transfers=execute_first_action(after,planned,meta);lineup=plan_squad(origin,list(after.squad),gw)
        result.update(ts_status='verified',ts_ran=True,plan=asdict(planned),transfers=transfers,lineup=json.loads(lineup.rows.to_json(orient='records')),
            chips_status='Not Available',blockers=['All four locked chip decisions require verified stopping-policy inputs and TC future-option scenarios.'])
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
