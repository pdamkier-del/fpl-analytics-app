import pytest
from fpl_v1_1_model.attack import shrunk_rate_per90,event_propensity,allocate_team_event_mean


def test_shrunk_rate_is_exposure_weighted():
    # 1 xG in 180 weighted minutes => 0.5/90; equal 180-minute prior at 0.2/90 => 0.35/90.
    r=shrunk_rate_per90(1.0,180.0,0.2,180.0)
    assert r == pytest.approx(0.35)


def test_propensity_uses_expected_minutes():
    assert event_propensity(45,0.4) == pytest.approx(0.2)


def test_team_allocation_conserves_team_mean():
    mu=allocate_team_event_mean(1.8,[.2,.3,.5])
    assert sum(mu) == pytest.approx(1.8)
    assert mu[2] > mu[1] > mu[0]


def test_zero_propensity_does_not_invent_events():
    assert allocate_team_event_mean(1.5,[0,0]) == [0.0,0.0]
