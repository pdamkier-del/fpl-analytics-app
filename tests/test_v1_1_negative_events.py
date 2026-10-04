import math
import numpy as np
import pytest
from fpl_v1_1_model.negative_events import (
    DisciplineProbabilities, LeagueDisciplineState, add_known_red_suspension,
    add_league_yellow, competing_card_probabilities, direct_negative_points,
    expected_direct_negative_points, rare_event_probability, sample_discipline,
    red_suspension_matches, serve_domestic_cup_match, serve_league_match, unavailable_for_next_pl_fixture,
)


def test_competing_cards_sum_and_scale_with_minutes():
    a=competing_card_probabilities(30,.30,.03)
    b=competing_card_probabilities(90,.30,.03)
    assert a.none+a.yellow+a.red == pytest.approx(1)
    assert b.yellow > a.yellow and b.red > a.red
    assert b.yellow/b.red == pytest.approx(10)


def test_rare_event_probability_poisson():
    assert rare_event_probability(90,.1) == pytest.approx(1-math.exp(-.1))
    assert rare_event_probability(0,.1) == 0


def test_direct_negative_scoring():
    assert direct_negative_points(yellow=1) == -1
    assert direct_negative_points(red=1) == -3
    assert direct_negative_points(own_goal=1,penalty_miss=1) == -4
    p=DisciplineProbabilities(.8,.15,.05)
    assert expected_direct_negative_points(p,p_own_goal=.01,p_penalty_miss=.02) == pytest.approx(-.15-.15-.02-.04)


def test_sampling_is_categorical():
    rng=np.random.default_rng(7);p=DisciplineProbabilities(.7,.2,.1)
    draws=[sample_discipline(rng,p) for _ in range(5000)]
    assert set(draws)=={'none','yellow','red'}
    assert abs(draws.count('red')/5000-.1)<.02


def test_yellow_suspension_state_machine():
    s=LeagueDisciplineState(yellows=4)
    s=add_league_yellow(s,19)
    assert s.yellows==5 and s.league_yellow_ban_matches==1 and s.served_five
    s=serve_league_match(s); assert s.league_yellow_ban_matches==0
    # threshold cannot trigger twice
    s=add_league_yellow(s,20); assert s.league_yellow_ban_matches==0
    s=LeagueDisciplineState(yellows=9,served_five=True)
    s=add_league_yellow(s,32); assert s.league_yellow_ban_matches==2 and s.served_ten
    s=LeagueDisciplineState(yellows=14,served_five=True,served_ten=True)
    s=add_league_yellow(s,38); assert s.league_yellow_ban_matches==3 and s.served_fifteen


def test_red_ban_length_and_cross_competition_serving():
    assert red_suspension_matches("second_caution")==1
    assert red_suspension_matches("violent_conduct")==3
    assert red_suspension_matches("violent_conduct",2)==4
    s=add_known_red_suspension(LeagueDisciplineState(),3)
    assert s.all_domestic_ban_matches==3 and unavailable_for_next_pl_fixture(s)
    s=serve_domestic_cup_match(s)
    assert s.all_domestic_ban_matches==2
    s=serve_league_match(s)
    assert s.all_domestic_ban_matches==1
    with pytest.raises(ValueError): add_known_red_suspension(s,-1)
    with pytest.raises(ValueError): red_suspension_matches("unknown")
