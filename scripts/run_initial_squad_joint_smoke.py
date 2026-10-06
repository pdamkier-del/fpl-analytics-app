#!/usr/bin/env python3
"""Smoke-test the new initial 6GW squad optimizer on the recovered rolling proxy.

This validates strategy mechanics only. The final initial squad must be driven
by rolling vFinal PM forecasts once those are available.
"""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import run_transfer_strategy_v3_replay as base
import run_horizon_policy_comparison as hp
from fpl_xpts.initial_squad_joint import InitialSquadConfig,optimize_initial_squad_joint

def main():
    gws,names,forecast=base.prepare()
    meta=hp.gw_meta(gws,names,1)
    origin=base.origin_with_meta(forecast,meta,1)
    res=optimize_initial_squad_joint(origin,meta,1,InitialSquadConfig())
    by=meta.set_index('id')
    out={
      'classification':'initial-squad optimizer smoke on Phase5Q proxy, not final vFinal squad',
      'objective':res.objective,'bank':res.bank_tenths/10,
      'squad':[{'id':i,'name':names.get(i,str(i)),'position':by.loc[i,'position'],'price':by.loc[i,'price_tenths']/10} for i in res.squad_ids],
      'captains':{str(gw):names.get(pid,str(pid)) for gw,pid in res.captains.items()},
      'vice_captains':{str(gw):names.get(pid,str(pid)) for gw,pid in res.vice_captains.items()},
      'lineups':{str(gw):[names.get(i,str(i)) for i in ids] for gw,ids in res.lineups.items()},
    }
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()
