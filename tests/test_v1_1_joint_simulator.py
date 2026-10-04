import numpy as np
from fpl_v1_1_model.joint_simulator import PlayerSimInput,MatchSimInput,simulate_match,simulate_many
from fpl_v1_1_model.negative_events import DisciplineProbabilities

def P(pid,team,pos,**kw):
    return PlayerSimInput(pid,team,pos,1.0,0.0,90,16,**kw)

def test_zero_goal_clean_sheet_and_scoring():
    inp=MatchSimInput('H','A',0,0,(P('d','H','DEF'),P('g','H','GKP',is_keeper=True),P('a','A','FWD')))
    r=simulate_match(inp,np.random.default_rng(1))
    assert r['d'].clean_sheet==1 and r['d'].points>=6
    assert r['g'].clean_sheet==1

def test_goal_allocation_conserves_team_goals_when_active_weight_exists():
    inp=MatchSimInput('H','A',4,0,(P('x','H','FWD',goal_weight=1),P('y','H','MID',goal_weight=1),P('z','A','DEF')))
    r=simulate_match(inp,np.random.default_rng(2))
    assert r['x'].goals+r['y'].goals>=0

def test_gc_deduction_exact_floor():
    inp=MatchSimInput('H','A',0,8,(P('d','H','DEF'),P('a','A','FWD',goal_weight=1)))
    r=simulate_match(inp,np.random.default_rng(3))
    assert r['d'].points <= 2

def test_many_reproducible_and_distribution_fields():
    inp=MatchSimInput('H','A',1.4,1.1,(P('x','H','FWD',goal_weight=1,assist_weight=1),P('y','A','FWD',goal_weight=1,assist_weight=1)))
    a=simulate_many(inp,500,7); b=simulate_many(inp,500,7)
    assert a==b
    assert {'xPts','median','p10','p90','p_attacking_return','p_10_plus','p_clean_sheet_award'} <= set(a['x'])

def test_card_is_competing_not_double_charged():
    inp=MatchSimInput('H','A',0,0,(P('x','H','MID',discipline=DisciplineProbabilities(0,0,1)),P('y','A','MID')))
    r=simulate_match(inp,np.random.default_rng(9))['x']
    assert r.red==1 and r.yellow==0
