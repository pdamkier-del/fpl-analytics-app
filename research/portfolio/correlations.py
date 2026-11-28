"""Compare pooled historical residuals and forecast conditional correlations."""
from collections import defaultdict
from itertools import combinations
import csv

import numpy as np


def category(pos_a, pos_b, same_team, same_fixture):
    roles = sorted((pos_a, pos_b))
    if same_team:
        if roles == [2, 2]:
            return 'DEF–DEF'
        if roles == [1, 2]:
            return 'GK–DEF'
        if roles == [3, 4]:
            return 'MID–FWD'
        if roles == [1, 1]:
            return 'GK slot competition'
    elif same_fixture:
        if roles == [2, 4]:
            return 'FWD–opposing DEF'
    else:
        return 'different fixtures'
    return None


def strength_features(rows):
    """Features use team scores and player returns from strictly past GWs."""
    team = defaultdict(list)
    player = defaultdict(list)
    x, y, groups = [], [], {}
    for gw in sorted({int(r['GW']) for r in rows}):
        current = [r for r in rows if int(r['GW']) == gw]
        fixtures = {}
        groups[gw] = []
        for r in current:
            club = r['team']
            home = r['was_home'] == 'True'
            # Derive opponent club names from the fixture sides below.
            fixtures.setdefault(r['fixture'], {})[home] = club
        results = {}
        for r in current:
            pos = ['GK', 'DEF', 'MID', 'FWD'].index(r['position']) + 1
            club, pid = r['team'], r['element']
            home = r['was_home'] == 'True'
            fixture = r['fixture']
            opposition = fixtures[fixture].get(not home)
            if opposition is None:
                continue
            gf, ga = (float(r[k]) for k in
                      (('team_h_score', 'team_a_score') if home else ('team_a_score', 'team_h_score')))
            attack, defense = np.mean(team[club][-8:] or [(1.5, 1.5)], axis=0)
            opp_attack, opp_defense = np.mean(team[opposition][-8:] or [(1.5, 1.5)], axis=0)
            recent = np.mean(player[pid][-8:] or [1.5])
            role = np.eye(4)[pos-1]
            x.append(np.outer(role, [1, home, attack, defense, opp_attack, opp_defense,
                                     recent]).ravel())
            groups[gw].append((len(y), club, pos, fixture, pid, float(r['minutes'])))
            y.append(float(r['total_points']))
            results[fixture, club] = (gf, ga)
        for (_, club), value in results.items():
            team[club].append(value)
        for idx, _, _, _, pid, _ in groups[gw]:
            player[pid].append(y[idx])
    return np.asarray(x), np.asarray(y), groups


def sufficient(a, b):
    return np.array([len(a), a.sum(), b.sum(), a@a, b@b, a@b])


def pooled(stats):
    n, x, y, xx, yy, xy = np.moveaxis(stats, -1, 0)
    with np.errstate(invalid='ignore', divide='ignore'):
        return (xy-x*y/n) / np.sqrt((xx-x*x/n)*(yy-y*y/n))


def historical(path, rng):
    with path.open(encoding='utf-8-sig') as stream:
        rows = [r for r in csv.DictReader(stream)
                if r['position'] in {'GK', 'DEF', 'MID', 'FWD'} and r['team_a_score']
                and r['team_h_score']]
    x, y, groups = strength_features(rows)
    output = defaultdict(list)
    for gw in sorted(groups):
        if gw <= 10:
            continue
        train = [r[0] for week in range(1, gw) for r in groups.get(week, [])]
        design = x[train]
        coef = np.linalg.solve(design.T@design + 10*np.eye(x.shape[1]), design.T@y[train])
        residual = y-x@coef
        by_fixture = defaultdict(list)
        for row in groups[gw]:
            by_fixture[row[3]].append(row)
        pairs = defaultdict(list)
        for players in by_fixture.values():
            for a, b in combinations(players, 2):
                key = category(a[2], b[2], a[1] == b[1], True)
                if key is not None:
                    pairs[key].append((a[0], b[0]))
        # Sample uniformly from different fixtures, excluding intra-GW duplicates by fixture.
        current = groups[gw]
        for i, j in rng.integers(len(current), size=(12000, 2)):
            a, b = current[i], current[j]
            if a[3] != b[3] and a[1] != b[1] and a[4] != b[4]:
                pairs['different fixtures'].append((a[0], b[0]))
        for key, indexes in pairs.items():
            a, b = np.asarray(indexes)[rng.permutation(len(indexes))].T.copy()
            swap = rng.random(len(a)) < .5
            a[swap], b[swap] = b[swap], a[swap].copy()
            output[key].append((sufficient(y[a], y[b]), sufficient(residual[a], residual[b])))
    result = {}
    for key, stats in output.items():
        a = np.asarray(stats)
        # Circular four-GW blocks retain short-range schedule and player dependence.
        starts = rng.integers(len(a), size=(1200, int(np.ceil(len(a)/4)), 1))
        sample = ((starts+np.arange(4)) % len(a)).reshape(1200, -1)[:, :len(a)]
        estimates = pooled(a.sum(axis=0))
        intervals = np.quantile(pooled(a[sample].sum(axis=1)), [.025, .975], axis=0).T
        result[key] = dict(pairs=int(a[:, 0, 0].sum()), gws=len(a),
                           raw=float(estimates[0]), adjusted=float(estimates[1]),
                           raw_ci=intervals[0].tolist(), adjusted_ci=intervals[1].tolist())
    return result


def simulated(archive, rng):
    values = defaultdict(list)
    for w, points in enumerate(archive.points):
        sd = points.std(axis=0, ddof=1)
        covariance = np.cov(points, rowvar=False)
        fixtures = [p['weeks'][w]['fixtures'] for p in archive.players]
        eligible = [i for i, f in enumerate(fixtures) if len(f) == 1 and sd[i] > 0]
        by_fixture = defaultdict(list)
        for i in eligible:
            by_fixture[fixtures[i][0]['fixture_uuid']].append(i)
        pairs = [pair for group in by_fixture.values() for pair in combinations(group, 2)]
        pairs.extend(rng.choice(eligible, size=(4000, 2)).tolist())
        seen = set()
        for i, j in pairs:
            pair = tuple(sorted((i, j)))
            if pair in seen or i == j:
                continue
            seen.add(pair)
            key = category(archive.positions[i], archive.positions[j],
                           archive.clubs[i] == archive.clubs[j],
                           fixtures[i][0]['fixture_uuid'] == fixtures[j][0]['fixture_uuid'])
            if key:
                values[key].append(covariance[i, j] / (sd[i]*sd[j]))
    return {key: dict(pairs=len(corr), mean=float(np.mean(corr)),
                      pair_quantiles=np.quantile(corr, [.1, .5, .9]).tolist())
            for key, corr in values.items()}
