"""Exact one-deadline budget frontiers using original player PM means."""
from collections import Counter
from dataclasses import dataclass
from itertools import product

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

QUOTAS = (2, 5, 5, 3)
FORMATIONS = tuple(
    (1, defenders, midfielders, forwards)
    for defenders, midfielders, forwards in product(range(3, 6), range(2, 6), range(1, 4))
    if defenders + midfielders + forwards == 10
)


def sale_price(purchase, market):
    """Prices are integer tenths of £m, including when a loss is realized."""
    if type(purchase) is not int or type(market) is not int or min(purchase, market) <= 0:
        raise ValueError("Expected positive integer prices in tenths of £m")
    return min(market, purchase + (market - purchase) // 2)


@dataclass(frozen=True)
class Player:
    id: int
    position: int
    club: int
    price: int
    points: float


@dataclass(frozen=True)
class Solution:
    points: float
    cost: int
    ids: tuple
    spending: tuple


def lineup_points(squad):
    points = [sorted((p.points for p in squad if p.position == position), reverse=True)
              for position in range(1, 5)]
    return max(sum(sum(group[:count]) for group, count in zip(points, formation))
               for formation in FORMATIONS) + max(group[0] for group in points)


def solution(squad, costs):
    return Solution(
        lineup_points(squad), sum(costs[p.id] for p in squad),
        tuple(sorted(p.id for p in squad)),
        tuple(sum(costs[p.id] for p in squad if p.position == pos) for pos in range(1, 5)),
    )


def global_squad(players, budget, costs):
    """Binary squad, starter, captain indicators. Require a certified optimum."""
    n = len(players)
    rows, lower, upper = [], [], []

    def add(entries, lo, hi):
        rows.append(entries)
        lower.append(lo)
        upper.append(hi)

    for pos, (quota, lo, hi) in enumerate(zip(QUOTAS, (1, 3, 2, 1), (1, 5, 5, 3)), 1):
        group = [i for i, p in enumerate(players) if p.position == pos]
        add({i: 1 for i in group}, quota, quota)
        add({n + i: 1 for i in group}, lo, hi)
    clubs = {}
    for i, player in enumerate(players):
        clubs.setdefault(player.club, {})[i] = 1
        add({n + i: 1, i: -1}, -np.inf, 0)
        add({2 * n + i: 1, n + i: -1}, -np.inf, 0)
    for group in clubs.values():
        add(group, -np.inf, 3)
    add({i: 1 for i in range(n, 2 * n)}, 11, 11)
    add({i: 1 for i in range(2 * n, 3 * n)}, 1, 1)
    add({i: costs[p.id] for i, p in enumerate(players)}, -np.inf, budget)
    matrix = lil_matrix((len(rows), 3 * n))
    for row, entries in enumerate(rows):
        for col, value in entries.items():
            matrix[row, col] = value
    points = np.array([p.points for p in players])
    result = milp(np.r_[np.zeros(n), -points, -points], integrality=np.ones(3 * n),
                  bounds=Bounds(0, 1), constraints=LinearConstraint(matrix.tocsc(), lower, upper),
                  options={"mip_rel_gap": 0.0, "time_limit": 90})
    if result.status == 2:
        return None
    if result.status != 0:
        raise RuntimeError(result.message)
    chosen = solution([p for i, p in enumerate(players) if result.x[i] > .5], costs)
    if chosen.cost > budget or abs(chosen.points + result.fun) > 1e-6:
        raise RuntimeError("Solver result failed independent score/budget check")
    return chosen


def local_options(players, purchase):
    """All legal zero/one-transfer outcomes, with the outgoing position."""
    owned = [p for p in players if p.id in purchase]
    clubs = Counter(p.club for p in owned)
    counts = Counter(p.position for p in owned)
    if tuple(counts[i] for i in range(1, 5)) != QUOTAS or max(clubs.values()) > 3:
        raise ValueError("Illegal initial squad or incomplete market")
    costs = {p.id: sale_price(purchase[p.id], p.price) if p.id in purchase else p.price
             for p in players}
    options = [(None, solution(owned, costs))]
    for outgoing in owned:
        keep = [p for p in owned if p.id != outgoing.id]
        for incoming in players:
            if incoming.id in purchase or incoming.position != outgoing.position:
                continue
            if clubs[incoming.club] - (outgoing.club == incoming.club) >= 3:
                continue
            options.append((outgoing.position, solution(keep + [incoming], costs)))
    return costs, options


def local_squad(options, budget, position=None):
    feasible = [s for pos, s in options if s.cost <= budget and
                (position is None or pos is None or pos == position)]
    return max(feasible, key=lambda s: (s.points, -s.cost, s.ids), default=None)
