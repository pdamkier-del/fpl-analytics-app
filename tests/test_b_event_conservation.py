from dataclasses import replace
import numpy as np
import pytest
from fpl_v1_1_model.joint_simulator import MatchSimInput,PlayerSimInput,PlayerSimResult
from fpl_v1_1_model.b_event_simulator import simulate_match,GoalEvent,attribute

def fixture():
    players=[]
    for team in ['h','a']:
        for i,pos in enumerate(['GK']+['DEF']*4+['MID']*4+['FWD']*2):
            players.append(PlayerSimInput(player_id=team+str(i),team=team,position=pos,p_start=1.,p_cameo_given_bench=0.,start_minutes_mean=90.,cameo_minutes_mean=15.,goal_weight=1.,assist_weight=1.,is_keeper=pos=='GK',penalty_weight=1. if i==10 else 0.,penalty_conversion=.5))
    inp=MatchSimInput('h','a',1.5,1.2,tuple(players),lambda_home_penalties=.2,home_penalty_conversion=.78,bps_rules='2026-27')
    return inp,{p.player_id:(90,0,90)for p in players}

def test_own_goal_changes_shared_score_concessions_clean_sheets_and_points():
    inp,t=fixture();inp=replace(inp,lambda_home_goals=0,lambda_away_goals=1,lambda_home_penalties=0,players=tuple(replace(p,p_own_goal=float(p.player_id=='h1'))for p in inp.players));trace={};out=simulate_match(inp,np.random.default_rng(4),timeline=t,trace=trace)
    assert trace['team_scores']=={'h':0,'a':1};assert trace['ordinary_intensity']=={'h':0.,'a':0.}
    assert out['h1'].own_goal==1 and out['a10'].goals==0
    assert all(out['h'+str(i)].clean_sheet==0 and out['h'+str(i)].goals_conceded_while_on_pitch==1 for i in range(11))
    assert out['h1'].points-out['h1'].bonus==0 # 2 appearance -2own goal, no CS.
    assert all(e.kind=='own_goal'for e in trace['events'])
    # Forced own goal with an inclusive zero opponent budget is contradictory.
    with pytest.raises(ValueError,match='budget'):simulate_match(replace(inp,lambda_away_goals=0),np.random.default_rng(4),timeline=t)

def test_no_phantom_scorer_or_assist_and_no_partial_roster():
    inp,t=fixture();bad=replace(inp,players=tuple(replace(p,goal_weight=0.)if p.team=='h'else p for p in inp.players),lambda_home_penalties=0,assist_probability_per_goal=1.)
    with pytest.raises(ValueError,match='eligible scorer'):simulate_match(bad,np.random.default_rng(1),timeline=t)
    with pytest.raises(ValueError):simulate_match(inp,np.random.default_rng(1),timeline={})
    out={p.player_id:PlayerSimResult()for p in inp.players}
    with pytest.raises(ValueError,match='scorer'):attribute(GoalEvent(10,'h','ordinary',assister='h1',assist_eligible=True),inp.players,out)

def test_conditional_penalty_budget_uses_actual_active_taker_conversion():
    inp,t=fixture();trace={};simulate_match(inp,np.random.default_rng(5),timeline=t,trace=trace)
    assert trace['penalty_conversion']['h']==.5
    assert trace['ordinary_intensity']['h']==pytest.approx(1.4)
    assert trace['ordinary_intensity']['h']+.2*.5==pytest.approx(1.5)
    with pytest.raises(ValueError,match='budget'):simulate_match(replace(inp,lambda_home_goals=.01),np.random.default_rng(5),timeline=t)

def test_explicit_penalty_and_own_goal_assist_rules():
    inp,t=fixture();out={p.player_id:PlayerSimResult()for p in inp.players}
    attribute(GoalEvent(10,'h','penalty','h10','h1',assist_eligible=True),inp.players,out)
    assert out['h10'].penalty_goals==1 and out['h1'].assists==1
    with pytest.raises(ValueError):attribute(GoalEvent(20,'h','penalty','h10','h10',assist_eligible=True),inp.players,out)
    attribute(GoalEvent(30,'h','own_goal',assister='h2',own_goal_committer='a1',assist_eligible=True),inp.players,out)
    assert out['a1'].own_goal==1 and out['h2'].assists==1

def test_penalty_conversion_tracks_the_taker_change_during_the_match():
    inp,t=fixture()
    players=tuple(replace(p,penalty_order=1,penalty_conversion=.9)if p.player_id=='h10'else p for p in inp.players)
    reserve=replace(players[10],player_id='h11',p_start=0.,p_cameo_given_bench=1.,penalty_order=2,penalty_conversion=.5)
    inp=replace(inp,players=players+(reserve,),experimental_penalty_hierarchy=True)
    t['h10']=(45,0,45);t['h11']=(45,45,90);trace={}
    simulate_match(inp,np.random.default_rng(7),timeline=t,trace=trace)
    assert trace['penalty_conversion']['h']==pytest.approx(.7)
    assert trace['ordinary_intensity']['h']+.2*.7==pytest.approx(1.5)
    assert trace['ordinary_intensity']['h']==pytest.approx(1.36)

def test_b_event_context_restores_the_original_simulator_after_failure():
    from fpl_v1_1_model import joint_simulator
    from fpl_v1_1_model.b_event_simulator import conserved_events
    original=joint_simulator.simulate_match
    with pytest.raises(RuntimeError):
        with conserved_events():
            assert joint_simulator.simulate_match is not original
            raise RuntimeError('deliberate worker failure')
    assert joint_simulator.simulate_match is original
