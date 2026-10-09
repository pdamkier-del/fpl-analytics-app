from __future__ import annotations
import numpy as np
import pandas as pd
from fpl_xpts.season_replay import ReplayState,OwnedPlayer,valid_squad,selling_price
from fpl_xpts.wildcard_planner_v2 import build_asof_wc_projection
from fpl_xpts.wildcard_ts_action import compare_wc_as_ts_action,_wc_milp_squads
from fpl_xpts.transfer_planner import PlannerConfig

CFG=PlannerConfig(weights=(1.0,.60,.36,.216,.1296,.07776))

def _data():
    positions=['GKP']*3+['DEF']*8+['MID']*9+['FWD']*5
    meta=pd.DataFrame([dict(id=i+1,web_name=str(i+1),team=(i//3)+1,
                            position=p,status='a',price_tenths=50)
                       for i,p in enumerate(positions)])
    chosen=[1,2,4,5,6,7,8,12,13,14,15,16,21,22,23]
    assert valid_squad(meta,chosen)
    state=ReplayState(squad={i:OwnedPlayer(i,40) for i in chosen},
                      bank=0,free_transfers=3)
    origin=pd.DataFrame([dict(id=int(i),gw=20,origin_gw=19,xpts_mean=5.,
                              p_play=.95,fixtures=1,position=p,web_name=str(i))
                         for i,p in zip(meta.id,meta.position)])
    earlier=origin.copy();earlier.gw=19;earlier.origin_gw=18;earlier.xpts_mean=4.
    return meta,state,origin,earlier,chosen


def test_wc_expanded_action_preserves_free_transfers_and_bank():
    meta,state,origin,earlier,owned=_data()
    proxy=build_asof_wc_projection(earlier,meta,origin,20,CFG)
    config=PlannerConfig(weights=(1.,.60,.36,.216,.1296,.07776),
                         candidate_limit_per_position=8,top_targets_per_position=8,
                         beam_width=2,local_bundle_beam=6,
                         candidate_return_per_depth=2,max_transfers_per_week=5)
    result=compare_wc_as_ts_action(state,meta,proxy,20,config,max_candidates=1,milp_seconds=5.)
    assert result.state.free_transfers==3
    assert state.free_transfers==3
    assert state.bank==0
    assert result.state.bank>=0
    assert valid_squad(meta,result.state.squad)
    assert result.candidates_tested>=1
    assert result.chosen_squad==tuple(sorted(result.state.squad))
    assert result.transfers==len(set(result.state.squad)-set(state.squad))
    assert result.state.chips_used['wildcard']==[20]
    assert result.normal_result.current_gw==20
    assert result.wc_objective>=0

def test_wc_milp_candidate_has_variable_lineups_across_future_gws():
    meta,state,origin,earlier,_=_data()
    projection=build_asof_wc_projection(earlier,meta,origin,20,CFG)
    # A new GK is strong in the first GW; an incumbent GK strong thereafter.
    # Candidate optimisation must allow weekly manager XI rotation.
    projection.loc[(projection.id==3)&(projection.gw==20),'xpts_mean']=20.
    projection.loc[(projection.id==1)&(projection.gw>20),'xpts_mean']=20.
    state.bank=20
    candidates=_wc_milp_squads(state,meta,projection,list(range(20,26)),
                               list(CFG.weights),1,5.,10)
    assert candidates
    assert valid_squad(meta,candidates[0])
    assert len(candidates[0])==15
