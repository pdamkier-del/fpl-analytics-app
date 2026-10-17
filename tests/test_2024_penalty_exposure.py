import pandas as pd
import pytest
from run_2024_25_conditional_pm import penalty_state

PARAMS={'selected':{'taker_half_life':3,'occurrence_tau':1,'conversion_tau':1}}


def test_occurrence_denominator_counts_games_without_penalties():
    fixtures=pd.DataFrame([dict(id=i,event=i,team_h=1,team_a=2,kickoff_time=f'2024-08-{i:02d}T12:00:00Z') for i in range(1,11)])
    events=pd.DataFrame([dict(gw=1,fixture_id=1,team_id=1,player_uuid='taker',attempts=1.,scored=1.)])
    _,rate=penalty_state(11,pd.DataFrame([{'player_uuid':'taker'}]),events,fixtures,PARAMS,cutoff=pd.Timestamp('2024-08-11',tz='UTC'))
    assert rate(1,2)==pytest.approx((1+.05)/11)
    assert rate(1,2)<.1


def test_delayed_prior_game_penalties_are_not_known_before_cutoff():
    fixtures=pd.DataFrame([dict(id=1,event=1,team_h=1,team_a=2,kickoff_time='2024-08-20T12:00:00Z'),dict(id=2,event=2,team_h=1,team_a=2,kickoff_time='2024-08-02T12:00:00Z')])
    events=pd.DataFrame([dict(gw=1,fixture_id=1,team_id=1,player_uuid='taker',attempts=1.,scored=1.)])
    players,rate=penalty_state(3,pd.DataFrame([{'player_uuid':'taker'}]),events,fixtures,PARAMS,cutoff=pd.Timestamp('2024-08-03',tz='UTC'))
    assert players['taker'][0]==0 and rate(1,2)==pytest.approx(1e-6)
