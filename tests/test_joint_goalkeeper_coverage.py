import numpy as np
from dataclasses import replace
from fpl_v1_1_model.joint_simulator import PlayerSimInput, MatchSimInput, simulate_match

def gk(pid,team,p):
    return PlayerSimInput(player_id=pid,team=team,position='GK',p_start=p,p_cameo_given_bench=0.,
        start_minutes_mean=90.,cameo_minutes_mean=15.,is_keeper=True)

def match(players,experiment=True):
    return MatchSimInput(home_team='H',away_team='A',lambda_home_goals=0.,
       lambda_away_goals=0.,players=tuple(players),experimental_joint_goalkeepers=experiment)

def test_one_keeper_covers_ninety():
    fixture=match([gk('Penders','H',.8),gk('away','A',1.)])
    for seed in range(40):
        out=simulate_match(fixture,np.random.default_rng(seed))
        assert out['Penders'].minutes==90
        assert out['Penders'].started==1
        assert out['away'].minutes==90

def test_two_goalkeepers_do_not_overlap_or_exceed_ninety():
    a=gk('one','H',.7)
    b=replace(gk('two','H',.3),p_cameo_given_bench=.7)
    a=replace(a,start_minutes_mean=50.,p_cameo_given_bench=.7)
    fixture=match([a,b,gk('away','A',1.)])
    for seed in range(100):
        out=simulate_match(fixture,np.random.default_rng(seed))
        assert out['one'].minutes+out['two'].minutes==90
        assert out['one'].started+out['two'].started==1

def test_default_stays_locked():
    assert match([gk('one','H',1.),gk('away','A',1.)],False).experimental_joint_goalkeepers is False
