import numpy as np
import pytest
from dataclasses import replace
from fpl_v1_1_model.joint_simulator import PlayerSimInput, MatchSimInput, simulate_match

def gk(pid,team,p):
    return PlayerSimInput(player_id=pid,team=team,position='GK',p_start=p,p_cameo_given_bench=0.,
        start_minutes_mean=90.,cameo_minutes_mean=15.,is_keeper=True)

def match(players,experiment=True):
    return MatchSimInput(home_team='H',away_team='A',lambda_home_goals=0.,
       lambda_away_goals=0.,players=tuple(players),experimental_joint_goalkeepers=experiment,
       verified_goalkeeper_roster_teams=("H", "A"))

def test_one_keeper_covers_ninety():
    fixture=match([gk('verified','H',1.),gk('away','A',1.)])
    for seed in range(40):
        out=simulate_match(fixture,np.random.default_rng(seed))
        assert out['verified'].minutes==90
        assert out['verified'].started==1
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


def test_unverified_sole_keeper_does_not_become_certain():
    fixture = replace(match([gk('Penders', 'H', .8), gk('away', 'A', 1.)]),
                      verified_goalkeeper_roster_teams=())
    with pytest.raises(ValueError, match='unverified goalkeeper roster'):
        simulate_match(fixture, np.random.default_rng(1))


@pytest.mark.parametrize('probabilities', [[.8], [.8,.4], [0.,0.]])
def test_start_mass_is_never_silently_normalized(probabilities):
    fixture = match([gk(str(i),'H',p) for i,p in enumerate(probabilities)] + [gk('away','A',1.)])
    with pytest.raises(ValueError, match='start mass'):
        simulate_match(fixture, np.random.default_rng(1))


def test_missing_reserve_cannot_force_injured_starter_to_ninety():
    fixture = match([replace(gk('one','H',1.),start_minutes_mean=70.), gk('away','A',1.)])
    with pytest.raises(ValueError, match='no eligible replacement'):
        simulate_match(fixture,np.random.default_rng(1))


@pytest.mark.parametrize('count', [2,3])
def test_joint_marginals_and_deterministic_conservation(count):
    from fpl_v1_1_model.joint_simulator import joint_goalkeeper_expected_minutes
    keepers = [replace(gk(str(i),'H',1/count), start_minutes_mean=80.25,
                       p_cameo_given_bench=.2) for i in range(count)]
    # A known absent keeper cannot start or replace another keeper.
    keepers.append(gk('absent','H',0.))
    means = joint_goalkeeper_expected_minutes(keepers,'H',('H',))
    assert sum(means.values()) == pytest.approx(90.)
    fixture = match(keepers + [gk('away','A',1.)])
    rng = np.random.default_rng(29)
    observed = {p.player_id:0 for p in keepers}
    for _ in range(2000):
        out = simulate_match(fixture,rng)
        assert sum(out[p.player_id].minutes for p in keepers) == 90
        assert sum(out[p.player_id].started for p in keepers) == 1
        assert out['absent'].minutes == 0
        for p in keepers:
            observed[p.player_id] += out[p.player_id].minutes / 2000
    for pid, mu in means.items():
        assert observed[pid] == pytest.approx(mu,abs=3.)
    assert simulate_match(fixture,np.random.default_rng(7)) == simulate_match(fixture,np.random.default_rng(7))
