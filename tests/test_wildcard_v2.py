from __future__ import annotations
import numpy as np
import pandas as pd
from fpl_xpts.season_replay import ReplayState,OwnedPlayer,valid_squad,selling_price
from fpl_xpts.wildcard_planner_v2 import build_asof_wc_projection,_solve_roster
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

def test_wc_pricing_cannot_force_sell_appreciated_incumbents():
    meta,state,origin,earlier,owned=_data()
    assert selling_price(40,50)==45
    proxy=build_asof_wc_projection(earlier,meta,origin,20,CFG)
    assert proxy.gw.nunique()==6
    roster=_solve_roster(state,meta,proxy,20,CFG)
    # 15 existing players cost 15*45 in sale equity. Replacements cost
    # 50, so an optimizer MUST be able to retain all originals.
    assert roster==set(owned)
    assert state.free_transfers==3 and state.bank==0

def test_wc_asof_forecast_cannot_use_future_origin():
    meta,state,origin,earlier,_=_data()
    future=earlier.copy();future.origin_gw=21;future.gw=22;future.xpts_mean=10000.
    baseline=build_asof_wc_projection(earlier,meta,origin,20,CFG)
    poisoned=build_asof_wc_projection(pd.concat([earlier,future],ignore_index=True),
                                      meta,origin,20,CFG)
    a=baseline.sort_values(['gw','id']).reset_index(drop=True)
    b=poisoned.sort_values(['gw','id']).reset_index(drop=True)
    pd.testing.assert_frame_equal(a,b)
    assert np.isfinite(b.xpts_mean).all()
    assert b.xpts_mean.max()<10000

def test_wc_no_silent_future_fixture_hindsight():
    meta,state,origin,earlier,_=_data()
    proxy=build_asof_wc_projection(earlier,meta,origin,20,CFG)
    assert set(proxy.gw)==set(range(20,26))
    assert (proxy.loc[proxy.gw.gt(20),'fixtures']==1).all()
