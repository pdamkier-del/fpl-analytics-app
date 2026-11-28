"""Research-only scoring and portfolio statistics."""
from dataclasses import dataclass
from itertools import combinations

import numpy as np


MINIMUM = np.array([1, 3, 2, 1])
MAXIMUM = np.array([1, 5, 5, 3])


@dataclass(frozen=True)
class Lineup:
    starters: tuple
    bench: tuple  # Reserve goalkeeper, then outfield players in priority order.
    captain: int
    vice: int


def score(points, minutes, positions, lineup, bench_boost=False, carded=None):
    """Score one GW, with player columns and aligned scenario rows."""
    points, minutes, positions = map(np.asarray, (points, minutes, positions))
    starters, bench = lineup.starters, lineup.bench
    squad = (*starters, *bench)
    if (len(starters) != 11 or len(bench) != 4 or len(set(squad)) != 15
            or lineup.captain == lineup.vice
            or not {lineup.captain, lineup.vice} <= set(starters)
            or positions[bench[0]] != 1
            or not np.array_equal(np.bincount(positions[list(squad)], minlength=5)[1:],
                                  [2, 5, 5, 3])):
        raise ValueError("Invalid lineup")
    formation = np.bincount(positions[list(starters)], minlength=5)[1:]
    if np.any(formation < MINIMUM) or np.any(formation > MAXIMUM):
        raise ValueError("Invalid formation")
    played = minutes > 0
    if carded is not None:
        played |= np.asarray(carded, dtype=bool)
    total = np.where(played, points, 0)[:, list(squad if bench_boost else starters)].sum(axis=1)
    if not bench_boost:
        goalkeeper = next(i for i in starters if positions[i] == 1)
        total += np.where(~played[:, goalkeeper] & played[:, bench[0]], points[:, bench[0]], 0)
        outfield = [i for i in starters if i != goalkeeper]
        absent = ~played[:, outfield]
        for pattern in np.unique(absent, axis=0):
            missing = [i for i, is_absent in zip(outfield, pattern) if is_absent]
            if not missing:
                continue
            rows = np.flatnonzero(np.all(absent == pattern, axis=1))
            filled = np.zeros(len(rows), dtype=bool)
            # Maximize number of legal substitutions, then apply bench priority.
            for size in range(min(3, len(missing)), 0, -1):
                legal_counts = [
                    np.bincount(positions[list(outgoing)], minlength=5)[1:]
                    for outgoing in combinations(missing, size)
                ]
                for incoming in combinations(bench[1:], size):
                    counts = np.bincount(positions[list(incoming)], minlength=5)[1:]
                    if not any(np.all((formation + counts - removed >= MINIMUM)
                                      & (formation + counts - removed <= MAXIMUM))
                               for removed in legal_counts):
                        continue
                    eligible = ~filled & played[np.ix_(rows, incoming)].all(axis=1)
                    total[rows[eligible]] += points[np.ix_(rows[eligible], incoming)].sum(axis=1)
                    filled |= eligible
    cap, vice = lineup.captain, lineup.vice
    return total + np.where(played[:, cap], points[:, cap],
                            np.where(played[:, vice], points[:, vice], 0))


def moments(points, weights):
    means = points.mean(axis=0)
    covariance = np.atleast_2d(np.cov(points, rowvar=False, ddof=1))
    return float(weights @ means), float(weights @ covariance @ weights)


def metrics(points, target, alpha=.1):
    """VaR/CVaR for loss defined as target minus score, including discrete atoms."""
    losses = np.sort(target - points)[::-1]
    mass = alpha * len(losses)
    whole = int(mass)
    boundary = int(np.ceil(mass)) - 1
    tail = (losses[:whole].sum() + (mass - whole) * losses[boundary]) / mass
    wins = np.count_nonzero(points > target)
    n = len(points)
    probability = wins / n
    z = 1.96
    center = (probability + z*z/(2*n)) / (1 + z*z/n)
    width = z * np.sqrt(probability*(1-probability)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return dict(mean=float(points.mean()), sd=float(points.std(ddof=1)),
                mean_mc_se=float(points.std(ddof=1)/np.sqrt(n)),
                quantiles=np.quantile(points, [.1, .5, .9]).tolist(),
                downside_rms=float(np.sqrt(np.mean(np.minimum(points-target, 0)**2))),
                var=float(losses[boundary]), cvar=float(tail),
                p_exceed=probability, p_exceed_mc_ci=[max(0., center-width), min(1., center+width)])
