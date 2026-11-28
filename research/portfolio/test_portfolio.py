import numpy as np
import pytest

from correlations import category, pooled, sufficient
from portfolio import Lineup, metrics, moments, score
from run import frontier


POSITIONS = np.array([1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4])
LINEUP = Lineup((0, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13), (1, 14, 5, 6), 12, 7)


def test_autosubs_and_captain():
    minutes = np.full((5, 15), 90)
    minutes[1, [0, 2, 12]] = 0
    minutes[2, [2, 5, 6]] = 0
    minutes[3, [7, 12]] = 0
    minutes[4, 12] = 1
    points = (minutes > 0) * np.arange(1, 16)
    original = points[:, LINEUP.starters].sum(axis=1)
    assert score(points, minutes, POSITIONS, LINEUP).tolist() == (
        original + [13, 2 + 6 + 15 + 8, 13, 15 + 6, 13]).tolist()
    assert score(points, minutes, POSITIONS, LINEUP, bench_boost=True).tolist() == (
        points.sum(axis=1) + [13, 8, 13, 0, 13]).tolist()


def test_card_without_minutes_occupies_slot_and_retains_captaincy():
    minutes = np.full((1, 15), 90)
    minutes[0, 12] = 0
    points = np.ones((1, 15))
    points[0, 12] = -1
    total = score(points, minutes, POSITIONS, LINEUP, carded=points < 0)
    assert total.item() == 8


def test_invalid_formation_is_rejected():
    invalid = Lineup((0, 2, 3, 7, 8, 9, 10, 11, 12, 13, 14), (1, 4, 5, 6), 12, 7)
    with pytest.raises(ValueError, match='formation'):
        score(np.ones((2, 15)), np.ones((2, 15)), POSITIONS, invalid)


def test_additive_mean_and_covariance_identity():
    points = np.array([[1, 1], [0, 6], [4, 0], [2, 8]])
    weights = np.array([1, 2])
    total = points @ weights
    assert moments(points, weights) == pytest.approx((total.mean(), total.var(ddof=1)))
    assert moments(points, weights)[0] == pytest.approx(
        moments(np.column_stack([points[:, 0], points[::-1, 1]]), weights)[0])


def test_discrete_cvar_and_strict_target():
    stats = metrics(np.array([1, 2, 3, 4, 5]), target=4, alpha=.3)
    assert stats['var'] == 2
    assert stats['cvar'] == pytest.approx((3 + .5*2)/1.5)
    assert stats['p_exceed'] == .2
    assert metrics(np.array([1, 2]), target=4, alpha=.1)['cvar'] == pytest.approx(3)


def test_pair_categories_pooled_correlation_and_frontier():
    assert category(2, 4, False, True) == 'FWD–opposing DEF'
    assert category(1, 1, True, True) == 'GK slot competition'
    a = np.array([1., 2., 5.])
    b = np.array([2., 0., 5.])
    assert pooled(sufficient(a, b)) == pytest.approx(np.corrcoef(a, b)[0, 1])
    assert frontier(np.array([3, 4, 5]), np.array([1, 1, 2])) == [1, 2]
