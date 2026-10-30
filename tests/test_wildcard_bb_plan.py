"""Conditional BB timing respects chip periods and the existing net uplift."""
import copy
from types import SimpleNamespace
import pytest
import service.wildcard_bb_plan as bb
from fpl_xpts.season_replay import ReplayState,OwnedPlayer

def setup_case(monkeypatch,gws=(10,11,12),gains=(12.,15.,20.),used=()):
    import fpl_xpts.optimize as opt
    import fpl_xpts.bench_boost_policy as policy
    import pandas as pd
    state=ReplayState({i:OwnedPlayer(i,50)for i in range(1,16)},0,2,{k:[]for k in ['wildcard','free_hit','bench_boost','triple_captain']});state.chips_used['wildcard']=[gws[0]-1];state.chips_used['bench_boost']=list(used)
    monkeypatch.setattr(bb,'_apply_selected_squad',lambda s,ids,m:(s,(),()))
    def plan(projection,ids,gw):return SimpleNamespace(expected_score=50.,rows=pd.DataFrame([{'gw':gw}]))
    def estimate(rows):
        gain=gains[gws.index(int(rows.gw.iloc[0]))]
        return SimpleNamespace(incremental_xp=gain,bench_xp=gain+3,expected_autosub_xp=3.,bench_player_ids=(12,13,14,15))
    monkeypatch.setattr(opt,'plan_squad',plan);monkeypatch.setattr(policy,'evaluate_bench_boost',estimate)
    f={'gw':gws[0]-1,'path':[dict(gw=g,outgoing=[],incoming=[],projected_manager_score=50.,official_hit_points=0,bank_after=0,free_transfers_after=2)for g in gws],'six_gw_xp_after_hits':50.*(len(gws)+1),'weighted_objective_before_chip_timing_threshold':100.}
    return state,f

def test_selects_one_positive_surplus_and_keeps_states_and_no_BB_scores(monkeypatch):
    state,f=setup_case(monkeypatch);before=copy.deepcopy(f);out=bb.add_bench_boost(f,state,None,None,[.6,.36,.216])
    assert f==before and state.chips_used['bench_boost']==[]
    chosen=[c for c in out['bench_boost']['candidates']if c['decision']=='USE_BB_PLANNED'];assert len(chosen)==1
    best=max(out['bench_boost']['candidates'],key=lambda c:c['weighted_net_value']);assert chosen==[best]
    assert out['six_gw_xp_after_hits']==f['six_gw_xp_after_hits']+best['incremental_xp']
    assert all(a['normal_projected_manager_score']==50 for a in out['path'])
    assert sum(a['chip']=='bench_boost'for a in out['path'])==1
    assert best['bench_xp']-best['normal_autosub_xp']==best['incremental_xp']

def test_used_chip_and_reserved_deadline_are_not_used(monkeypatch):
    state,f=setup_case(monkeypatch,used=(5,));out=bb.add_bench_boost(f,state,None,None,[.6,.36,.216]);assert out['bench_boost']['selected_gws']==[];assert out['bench_boost']['status']=='unavailable'
    state,f=setup_case(monkeypatch);out=bb.add_bench_boost(f,state,None,None,[.6,.36,.216],reserved_chip_gws=(10,11,12));assert out['bench_boost']['selected_gws']==[]

def test_no_forced_BB_below_locked_threshold_even_with_positive_bench_points(monkeypatch):
    state,f=setup_case(monkeypatch,gains=(1.,1.,1.));out=bb.add_bench_boost(f,state,None,None,[.6,.36,.216]);assert out['bench_boost']['status']=='save';assert out['six_gw_xp_after_hits']==f['six_gw_xp_after_hits']

def test_chip_period_reset_allows_one_in_each_period(monkeypatch):
    state,f=setup_case(monkeypatch,gws=(19,20,21),gains=(20.,30.,30.));out=bb.add_bench_boost(f,state,None,None,[.6,.36,.216]);assert out['bench_boost']['selected_gws']==[19,20]

def test_same_WC_deadline_is_rejected(monkeypatch):
    state,f=setup_case(monkeypatch);f['gw']=10
    with pytest.raises(ValueError,match='follow WC'):bb.add_bench_boost(f,state,None,None,[.6,.36,.216])
