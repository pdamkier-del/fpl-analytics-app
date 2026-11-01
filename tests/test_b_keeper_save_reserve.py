"""Inclusive-save conservation when active penalty takers/keepers change."""
from dataclasses import replace
import numpy as np
import pytest
from fpl_v1_1_model import experimental_keeper_save_reserve as B
from secondary_save_sensitivity import fixture


@pytest.mark.parametrize('conversion',[(.1,.9),(.9,.1),(.5,.5)])
def test_each_keeper_reserves_only_penalties_during_his_own_stint(conversion):
    inp,t=fixture(True,2.,conversion)
    intervals={p:(v[1],v[2]) for p,v in t.items()}
    by={p.player_id:p for p in inp.players}
    for pid,conv in zip(('a0','a11'),conversion):
        regular=B.regular_save_mean(inp,by[pid],intervals,{'h':1.,'a':0.},{'h':sum(conversion)/2,'a':conversion[0]})
        assert regular+.5*(1-conv)==pytest.approx(1.)


def test_simulator_passes_stint_specific_regular_means_to_count_sampler(monkeypatch):
    inp,t=fixture(True,2.,(.1,.9));seen=[]
    monkeypatch.setattr(B.B.legacy,'_sample_calibrated_saves',lambda rng,mu,tilts:seen.append(mu) or 0)
    B.simulate_match(inp,np.random.default_rng(4),timeline=t)
    # h0 has no opponent penalties, followed by the two away keepers.
    assert seen==pytest.approx([2.,.55,.95])


def test_full_match_keeper_retains_established_mean_and_infeasible_zero_floor():
    inp,t=fixture(False,2.,(.1,.9));p=next(p for p in inp.players if p.player_id=='a0')
    intervals={p:(v[1],v[2]) for p,v in t.items()}
    for lam in (0.,.2,2.):
        q=replace(p,lambda_saves=lam)
        mean=B.regular_save_mean(inp,q,intervals,{'h':1.,'a':0.},{'h':.5,'a':.1})
        assert mean==max(0.,lam-.5)


def test_no_penalty_save_probability_and_no_attempts_do_not_reduce_regular_saves():
    inp,t=fixture(True,2.,(.1,.9));p=next(p for p in inp.players if p.player_id=='a0')
    intervals={p:(v[1],v[2]) for p,v in t.items()}
    assert B.regular_save_mean(replace(inp,p_penalty_save_given_miss=0.),p,intervals,{'h':1.,'a':0.},{'h':.5,'a':.1})==1.
    assert B.regular_save_mean(inp,p,intervals,{'h':0.,'a':0.},{'h':.5,'a':.1})==1.


def test_partial_keeper_with_constant_taker_law_matches_old_formula():
    inp,t=fixture(True,2.,(.5,.5));p=next(p for p in inp.players if p.player_id=='a0')
    intervals={p:(v[1],v[2]) for p,v in t.items()}
    assert B.regular_save_mean(inp,p,intervals,{'h':1.,'a':0.},{'h':.5,'a':.5})==pytest.approx(.75)


@pytest.mark.parametrize('goal_time,departing_cs',[(59.999,0),(60.,1),(75.,1)])
def test_own_goal_at_substitution_boundary_uses_player_interval(goal_time,departing_cs):
    inp,t=fixture(False,2.,(.5,.5))
    # Remove the synthetic penalty-taker substitution before adding a defender.
    players=tuple(p for p in inp.players if p.player_id!='h11')
    t.pop('h11');t['h10']=(90,0,90)
    substitute=replace(next(p for p in players if p.player_id=='h2'),player_id='h12',p_start=0.)
    players=tuple(replace(p,p_own_goal=float(p.player_id=='h1')) for p in players)+(substitute,)
    inp=replace(inp,players=players,lambda_home_goals=0.,lambda_away_goals=1.,lambda_home_penalties=0.)
    t['h2']=(60,0,60);t['h12']=(30,60,90)
    class FixedGoalTime:
        def __init__(self):self.rng=np.random.default_rng(1)
        def __getattr__(self,name):return getattr(self.rng,name)
        def uniform(self,a,b):
            assert a<=goal_time<b
            return goal_time
    result=B.simulate_match(inp,FixedGoalTime(),timeline=t)
    assert result['h2'].clean_sheet==departing_cs
    assert result['h2'].goals_conceded_while_on_pitch==1-departing_cs
    assert result['h12'].clean_sheet==0
    assert result['h0'].clean_sheet==0
    assert result['h1'].own_goal==1


def test_shared_rank_takers_use_the_event_samplers_weighted_conversion():
    inp,t=fixture(True,2.,(.1,.9))
    inp=replace(inp,players=tuple(replace(p,penalty_order=1,penalty_weight=3.,penalty_conversion=.9) if p.player_id=='h9' else p for p in inp.players))
    intervals={p:(v[1],v[2]) for p,v in t.items()};by={p.player_id:p for p in inp.players}
    conv={'h':.8,'a':.1};attempts={'h':1.,'a':0.}
    assert B.regular_save_mean(inp,by['a0'],intervals,attempts,conv)==pytest.approx(.85)
    assert B.regular_save_mean(inp,by['a11'],intervals,attempts,conv)==pytest.approx(.95)


def test_opt_in_restores_sealed_b_after_failure():
    from fpl_v1_1_model import b_event_simulator as sealed
    original=sealed.simulate_match
    with pytest.raises(RuntimeError,match='deliberate'):
        with B.keeper_save_reserve():
            assert sealed.simulate_match is B.simulate_match
            raise RuntimeError('deliberate')
    assert sealed.simulate_match is original
