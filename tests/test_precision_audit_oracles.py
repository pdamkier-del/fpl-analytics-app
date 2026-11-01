"""Oracle identities and conditioning, independent of any release activation."""
from dataclasses import replace
import numpy as np
import pytest
from precision_audit.oracles import own_subset,pb_suffix,simulate,actual_timeline
from fpl_v1_1_model import b_event_simulator as B
from test_b_event_conservation import fixture

def test_conditioned_score_is_exact_for_zero_and_multi_goal_outcomes():
    inp,timeline=fixture();original=B.simulate_match
    for goals in [{'h':0,'a':0},{'h':3,'a':1}]:
        for seed in range(8):
            out=simulate(inp,np.random.default_rng(seed),timeline,goals)
            for team in ['h','a']:
                total=sum(out[p.player_id].goals for p in inp.players if p.team==team)+sum(out[p.player_id].own_goal for p in inp.players if p.team!=team)
                assert total==goals[team]
    assert B.simulate_match is original

def test_oracle_without_score_uses_unchanged_B_events_and_rng():
    inp,t=fixture();a=np.random.default_rng(7);b=np.random.default_rng(7)
    assert simulate(inp,a,t)==B.simulate_match(inp,b,timeline=t)
    assert a.bit_generator.state==b.bit_generator.state

def test_own_goal_conditioning_respects_forced_and_impossible_scores():
    assert pb_suffix([.2,.3])[0].sum()==pytest.approx(1)
    assert own_subset([1.],1,0,np.random.default_rng(1))==[0]
    with pytest.raises(ValueError):own_subset([0.],1,0,np.random.default_rng(1))

def test_actual_clock_rejects_fpl_stoppage_minute_inconsistency():
    inp,t=fixture();actual={p.player_id:dict(minutes=90,started=1)for p in inp.players}
    assert actual_timeline(inp,actual)==t
    actual['h1']['minutes']=89
    with pytest.raises(ValueError):actual_timeline(inp,actual)


def test_two_clocks_keep_fpl_minutes_without_forcing_990():
    from precision_audit.oracles import reconcile_timeline
    inp,t=fixture();actual={p.player_id:dict(minutes=90,started=1)for p in inp.players}
    actual['h1']['minutes']=89
    physical,error=reconcile_timeline(inp,actual,True)
    assert sum(v[0]for p,v in physical.items()if p.startswith('h'))==990
    observed={p:r['minutes']for p,r in actual.items()}
    out=simulate(inp,np.random.default_rng(3),physical,point_minutes=observed)
    assert out['h1'].minutes==89 and error['h1']==1
