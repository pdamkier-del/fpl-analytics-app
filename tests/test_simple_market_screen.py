"""Independent mathematical checks for the offline market research screen."""
import numpy as np
import pytest
from scipy.stats import poisson, skellam
from analysis.screen_simple_market_model import fair, implied_means, project


def test_market_inversion_recovers_known_independent_poisson_rates():
    h,a=2.1,.85
    outcome=np.array([skellam.sf(0,h,a),skellam.pmf(0,h,a),skellam.cdf(-1,h,a)])
    total=np.array([poisson.sf(2,h+a),poisson.cdf(2,h+a)])
    means,residual=implied_means(np.r_[1/(outcome*1.06),1/(total*1.04)])
    assert means==pytest.approx([h,a],abs=1e-6)
    assert residual<1e-7


def test_starter_projection_preserves_ranking_and_exact_count():
    raw=np.linspace(.01,.95,25)
    p=project(raw,10)
    assert p.sum()==pytest.approx(10,abs=1e-10)
    assert np.all(np.diff(p)>0)
    assert np.all((p>0)&(p<1))


@pytest.mark.parametrize('odds',[[1,2],[0,2],[float('nan'),2],[float('inf'),2]])
def test_invalid_odds_fail_closed(odds):
    with pytest.raises(ValueError):fair(odds)


def test_impossible_starter_projection_fails_closed():
    with pytest.raises(ValueError):project([.5,.5],3)


def test_analytic_forward_expectation_and_nonappearance():
    from fpl_v1_1_model.joint_simulator import PlayerSimInput, MatchSimInput
    from analysis.screen_simple_market_model import expected_points
    from dataclasses import replace
    p=PlayerSimInput('a','h','FWD',1,0,90,10,goal_weight=1)
    absent=replace(p,player_id='absent',p_start=0)
    q=replace(p,player_id='b',team='a')
    inp=MatchSimInput('h','a',2,1,players=(p,absent,q),assist_probability_per_goal=0)
    full=np.zeros(91);full[90]=1
    zero=np.zeros(91);zero[0]=1
    points=expected_points(inp,{'a':full,'absent':zero,'b':full},[2,1],{})
    assert points['a']==pytest.approx(2+4*2)
    assert points['b']==pytest.approx(2+4*1)
    assert points['absent']==0
