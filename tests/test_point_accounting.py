"""FPL-rule examples independent of the simulation implementation."""
import pytest
from fpl_v1_1_model.joint_simulator import PlayerSimResult
from fpl_v1_1_model.point_accounting import point_components,nonbonus_total


@pytest.mark.parametrize('position,goal_points,cs_points',[('GK',10,4),('GKP',10,4),('DEF',6,4),('MID',5,1),('FWD',4,0)])
def test_position_goal_and_clean_sheet_rules(position,goal_points,cs_points):
    r=PlayerSimResult(minutes=90,goals=1,assists=1,clean_sheet=1)
    c=point_components(position,position in ('GK','GKP'),r)
    assert nonbonus_total(c)==2+goal_points+3+cs_points


@pytest.mark.parametrize('minutes,appearance',[(0,0),(1,1),(59,1),(60,2),(90,2)])
def test_appearance_threshold(minutes,appearance):
    assert nonbonus_total(point_components('MID',False,PlayerSimResult(minutes=minutes)))==appearance


def test_penalty_miss_is_exposed_but_charged_once():
    c=point_components('MID',False,PlayerSimResult(minutes=90,penalty_miss=1))
    assert c['penalty_miss_pts']==c['negative_pts']==-2
    assert nonbonus_total(c)==0


def test_keeper_save_buckets_and_conceded_goal_floor():
    r=PlayerSimResult(minutes=90,saves=8,penalty_saves=1,goals_conceded_while_on_pitch=3)
    assert nonbonus_total(point_components('GK',True,r))==2+2+5-1


def test_defensive_contribution_and_negative_events():
    r=PlayerSimResult(minutes=90,dc_points=2,yellow=1,own_goal=1,goals_conceded_while_on_pitch=2)
    assert nonbonus_total(point_components('DEF',False,r))==2+2-1-2-1


def test_nonappearance_cannot_leak_other_event_points():
    r=PlayerSimResult(minutes=0,goals=1,assists=1,saves=9,penalty_miss=1,bonus=3)
    assert all(v==0 for v in point_components('GK',True,r).values())
