from datetime import datetime,timedelta,timezone
import pytest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from experimental_individual_dc_propensity import player_dc_propensity,projected_dc_mean
T=datetime(2025,10,15,tzinfo=timezone.utc)
def obs(days,n,m=90,e=1.):
    return {"known_at":T-timedelta(days=days),"minutes":m,"dc_count":n,"exposure_multiplier":e}
def test_unobserved_matches_preserve_role_prior():
    z=player_dc_propensity([],T,role_rate90=7.)
    assert z["neutral_dc_rate90"]==7.
def test_players_with_more_actions_have_higher_rates():
    low=player_dc_propensity([obs(1,3),obs(2,4)],T,6.)
    high=player_dc_propensity([obs(1,9),obs(2,10)],T,6.)
    assert high["neutral_dc_rate90"]>low["neutral_dc_rate90"]
def test_opponent_exposure_not_misattributed_to_player():
    a=player_dc_propensity([obs(1,10,e=2.)],T,5.)
    b=player_dc_propensity([obs(1,10,e=1.)],T,5.)
    assert a["neutral_dc_rate90"]<b["neutral_dc_rate90"]
def test_future_events_are_excluded():
    base=[obs(1,6)]
    future={"known_at":T+timedelta(days=1),"minutes":90,"dc_count":50}
    assert player_dc_propensity(base,T,6.)==player_dc_propensity(base+[future],T,6.)
def test_opponent_opportunities_raise_counts_not_rate():
    z=player_dc_propensity([obs(1,8)],T,6.)["neutral_dc_rate90"]
    assert projected_dc_mean(z,90,1.3)==pytest.approx(1.3*projected_dc_mean(z,90,1.))
def test_invalid_missing_data_does_not_become_zero():
    with pytest.raises((KeyError,TypeError,ValueError)):
        player_dc_propensity([{"known_at":T,"minutes":90}],T,6.)
    with pytest.raises(ValueError):
        projected_dc_mean(5,91)
