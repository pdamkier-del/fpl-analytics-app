"""Offline experiment using a recovered, verified PM forecast."""
import argparse
import gzip
import hashlib
from itertools import combinations
import json
from pathlib import Path

import numpy as np

from correlations import historical, simulated
from portfolio import Lineup, metrics, moments, score


class Archive:
    def __init__(self, path):
        data = json.loads(gzip.decompress(path.read_bytes()))
        if data['scenario_contract']['version'] != 'shared-PM-match-draws-v1':
            raise ValueError('Expected shared PM draws')
        self.players = data['players']
        self.gws = data['gws']
        self.clubs = np.array([p['team_id'] for p in self.players])
        self.positions = np.array([p['position'] for p in self.players])
        self.prices = np.array([p['price_tenths'] for p in self.players])
        self.points, self.minutes = (
            np.array([[p['weeks'][w]['scenarios'][key] for p in self.players]
                      for w in range(len(self.gws))]).transpose(0, 2, 1)
            for key in ('points', 'minutes'))


def candidate_squads(archive, means, rng):
    """Deterministic seeded search, followed by a one-transfer neighborhood."""
    horizon = means.mean(axis=0)
    eligible = [np.flatnonzero((archive.positions == pos) & (horizon > 0))
                for pos in range(1, 5)]
    candidates = []
    for _ in range(3200):
        squad = []
        for pool, quantity in zip(eligible, [2, 5, 5, 3]):
            weights = np.maximum(horizon[pool], .1)**2
            squad.extend(rng.choice(pool, quantity, replace=False, p=weights/weights.sum()))
        if archive.prices[squad].sum() <= 1000 and np.bincount(archive.clubs[squad]).max() <= 3:
            candidates.append(squad)
    base = max(candidates, key=lambda squad: sum(horizon[squad]))
    neighbors = [tuple(sorted(base))]
    for slot, player in enumerate(base):
        pool = eligible[archive.positions[player]-1]
        for i in pool[np.argsort(horizon[pool])[-15:]]:
            if i in base:
                continue
            squad = base.copy()
            squad[slot] = i
            if (archive.prices[squad].sum() <= archive.prices[base].sum()
                    and np.bincount(archive.clubs[squad]).max() <= 3):
                neighbors.append(tuple(sorted(squad)))
    return neighbors


def pick_lineup(squad, positions, mean):
    ranked = sorted(squad, key=lambda i: (-mean[i], i))
    options = []
    for defenders in range(3, 6):
        for mids in range(2, 6):
            forwards = 10-defenders-mids
            if 1 <= forwards <= 3:
                starters = tuple(i for pos, count in enumerate([1, defenders, mids, forwards], 1)
                                 for i in [i for i in ranked if positions[i] == pos][:count])
                options.append(starters)
    starters = max(options, key=lambda xi: sum(mean[list(xi)]))
    reserves = [i for i in ranked if i not in starters]
    keeper = next(i for i in reserves if positions[i] == 1)
    cap, vice = [i for i in ranked if i in starters][:2]
    return Lineup(starters, (keeper, *[i for i in reserves if i != keeper]), cap, vice)


def frontier(means, sds):
    return [i for i in range(len(means)) if not np.any(
        (means >= means[i]) & (sds <= sds[i]) & ((means > means[i]) | (sds < sds[i])))]


def experiment(a, rng):
    count = a.points.shape[1]
    order = rng.permutation(count)
    train, test = np.array_split(order, 2)
    means = a.points[:, train].mean(axis=1)
    squads = candidate_squads(a, means, rng)
    lineups = [[pick_lineup(s, a.positions, means[w]) for s in squads]
               for w in range(len(a.gws))]
    returns = np.array([[score(a.points[w], a.minutes[w], a.positions, lineup)
                         for lineup in group] for w, group in enumerate(lineups)])
    training = returns[:, :, train].sum(axis=0)
    mean, sd = training.mean(axis=1), training.std(axis=1, ddof=1)
    best = int(mean.argmax())
    tolerances = [0, .25, .5, 1, 2, 4]
    low = [int(np.argmin(np.where(mean >= mean[best]-delta, sd, np.inf)))
           for delta in tolerances]
    target = float(np.ceil(mean[best] + sd[best]*.5))
    high = int((training > target).mean(axis=1).argmax())
    screened = frontier(mean, sd)
    subsets = dict(A=best, B=low[3], C=high)
    held = returns[:, :, test].sum(axis=0)
    components = []
    for w, lineup in enumerate(row[best] for row in lineups):
        weights = np.zeros(len(a.players))
        weights[list(lineup.starters)] = 1
        weights[lineup.captain] += 1
        pts = a.points[w, test]
        mu, var = moments(pts, weights)
        squared = (weights**2) @ pts.var(axis=0, ddof=1)
        total = pts @ weights
        assert np.allclose([mu, var], [total.mean(), total.var(ddof=1)])
        components.append(dict(gw=a.gws[w], mean=mu, joint_var=var, independent_var=float(squared)))
    covariance_validation = []
    independent = []
    covariances = []
    for w, lineup in enumerate(row[best] for row in lineups):
        ids = list(squads[best])
        pts = a.points[w][:, ids]
        mins = a.minutes[w][:, ids]
        positions = a.positions[ids]
        rel = Lineup(tuple(ids.index(i) for i in lineup.starters),
                     tuple(ids.index(i) for i in lineup.bench),
                     ids.index(lineup.captain), ids.index(lineup.vice))
        permutations = np.column_stack([rng.permutation(test) for i in ids])
        independent.append(score(np.take_along_axis(pts, permutations, axis=0),
                                 np.take_along_axis(mins, permutations, axis=0),
                                 positions, rel))
        covariances.append(np.cov(pts[train], rowvar=False))
    for w, (covariance, lineup) in enumerate(zip(covariances, (row[best] for row in lineups))):
        ids = list(squads[best])
        weights = np.array([int(i in lineup.starters) + int(i == lineup.captain) for i in ids])
        assert np.linalg.eigvalsh(covariance).min() >= -1e-10
        diagonal = np.diag(np.diag(covariance))
        covariance_validation.append(dict(gw=a.gws[w],
            predicted_var={str(gamma): float(weights @ ((1-gamma)*covariance + gamma*diagonal) @ weights)
                           for gamma in [0, .25, .5, .75, 1]},
            heldout_var=components[w]['joint_var']))
    concentrated = np.array([sum(v*(v-1)//2 for v in np.bincount(a.clubs[list(s)]))
                             for s in squads])
    cutoff = mean[best]-4
    near = np.flatnonzero(mean >= cutoff)
    for key, preference in [('stacked', 1), ('spread', -1)]:
        subsets[key] = int(max(near, key=lambda i: (preference*concentrated[i], mean[i])))
    rival = int(max((i for i in range(len(squads)) if i != best), key=lambda i: mean[i]))
    phases = {}
    paths = {}
    bootstrap = rng.integers(len(test), size=(2000, len(test)))
    six_gw = {}
    for key, i in subsets.items():
        delta = held[i] - held[best]
        six_gw[key] = metrics(held[i], target)
        six_gw[key]['delta_mean_vs_A'] = float(delta.mean())
        six_gw[key]['delta_mean_vs_A_mc_ci'] = np.quantile(delta[bootstrap].mean(axis=1),
                                                         [.025, .975]).tolist()
    for label, weeks in [('season_stress', 38), ('early', 24), ('middle', 12), ('late', 6)]:
        n_paths = 6000
        draw = rng.choice(test, (weeks, n_paths))
        target_total = float(np.ceil(target*weeks/len(a.gws)))
        paths[label] = {}
        phases[label] = {}
        for strategy in [*subsets, 'D_chase', 'D_defend', 'E_chase', 'E_defend', 'rolling_mean_chase', 'rolling_mean_defend']:
            running = np.zeros(n_paths)
            gap = np.full(n_paths, -12. if strategy.endswith('chase') else 12.)
            idx = np.full(n_paths, best)
            swaps = np.zeros(n_paths)
            legal = np.array([[len(set(s) - set(t)) <= 1 and
                               a.prices[list(t)].sum() <= a.prices[list(s)].sum()
                               for t in squads] for s in squads])
            for step in range(weeks):
                w = step % len(a.gws)
                if strategy in subsets:
                    idx[:] = subsets[strategy]
                else:
                    # D makes one decision at the start;
                    # E re-evaluates after each observed GW, within one free transfer.
                    horizon = min(len(a.gws), weeks-step)
                    block = [(step+k) % len(a.gws) for k in range(horizon)]
                    relative = (returns[block][:, :, train] -
                                returns[block][:, rival:rival+1, train]).sum(axis=0)
                    if not strategy.startswith('D') or step == 0:
                        for deficit in np.unique(gap):
                            rows = np.flatnonzero(gap == deficit)
                            objective = (relative.mean(axis=1) if strategy.startswith('rolling_mean')
                                         else (relative + deficit > 0).mean(axis=1))
                            choices = np.lexsort((-mean, -objective))
                            next_idx = choices[np.argmax(legal[idx[rows]][:, choices], axis=1)]
                            swaps[rows] += next_idx != idx[rows]
                            idx[rows] = next_idx
                earned = returns[w, idx, draw[step]]
                running += earned
                gap += earned - returns[w, rival, draw[step]]
            paths[label][strategy] = running
            summary = metrics(running, target_total)
            summary['mean_transfers_from_A'] = float(swaps.mean()) if strategy not in subsets else None
            summary['mean_delta_vs_A'] = float((running-paths[label]['A']).mean())
            if strategy not in subsets:
                summary['rival_strict_win'] = metrics(gap, 0)['p_exceed']
                summary['rival_mc_ci'] = metrics(gap, 0)['p_exceed_mc_ci']
            phases[label][strategy] = summary
    report = dict(candidate_count=len(squads), six_gw_target=target,
                  six_gw=six_gw,
                  mean_slack=[dict(points=d, candidate=i, heldout=metrics(held[i], target))
                              for d, i in zip(tolerances, low)],
                  tail_sensitivity={key: {str(alpha): metrics(held[i], target, alpha)['cvar']
                                          for alpha in [.05, .1, .2]}
                                    for key, i in subsets.items()},
                  threshold_sensitivity={str(target+d): {
                      key: float(np.mean(held[i] > target+d)) for key, i in subsets.items()}
                      for d in [-20, -10, 0, 10, 20]},
                  phases=phases, additive_check=components,
                  covariance_validation=covariance_validation,
                  independent_ablation_A=metrics(np.sum(independent, axis=0), target),
                  rival_candidate=rival, selected_candidates=subsets,
                  same_club_pairs={k: int(concentrated[i]) for k, i in subsets.items()},
                  mean_variance_grid={str(lam): int(np.argmax(mean-lam*sd**2))
                                      for lam in [0, .001, .0025, .005, .01, .025, .05, .1]})
    return report, (mean, sd, screened), paths, lineups[0][best], test


def write_figures(out, archive, line, test, mf, paths):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    ids = line.starters
    matrix = np.cov(archive.points[0, test][:, ids], rowvar=False)
    fig, ax = plt.subplots(figsize=(8, 7), layout='constrained')
    limit = np.max(np.abs(matrix))
    im = ax.imshow(matrix, cmap='RdBu_r', vmin=-limit, vmax=limit)
    labels = [archive.players[i]['name'] for i in ids]
    ax.set_xticks(range(len(ids)), labels, rotation=55, ha='right')
    ax.set_yticks(range(len(ids)), labels)
    ax.set_title(f'GW{archive.gws[0]} · PM-kovarians for A’s startellever')
    fig.colorbar(im, ax=ax, label='Point²')
    fig.savefig(out/'covariance.png', dpi=140)
    plt.close(fig)

    mean, sd, front = mf
    front = sorted(front, key=lambda i: sd[i])
    fig, ax = plt.subplots(layout='constrained')
    ax.scatter(sd, mean, color='gray', alpha=.5, label='Kandidater')
    ax.plot(sd[front], mean[front], 'o-', color='#276149', label='Efficient frontier')
    ax.set(xlabel='Standardafvigelse (point)', ylabel='Forventede point',
           title='Seks GWs · træningstræk')
    ax.legend()
    fig.savefig(out/'frontier.png', dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(layout='constrained')
    for key, values in paths['season_stress'].items():
        if key in {'A', 'stacked', 'spread', 'E_chase', 'E_defend'}:
            ax.hist(values, bins=40, density=True, histtype='step', linewidth=1.5, label=key)
    ax.set(xlabel='Point over 38 GWs', ylabel='Tæthed',
           title='Sæsonstresstest · gentagne GW12–17-profiler')
    ax.legend()
    fig.savefig(out/'season.png', dpi=140)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('forecast', type=Path)
    parser.add_argument('history', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--second-forecast', type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    archive = Archive(args.forecast)
    rng = np.random.default_rng(20261128)
    report, mf, paths, line, test = experiment(archive, rng)
    report['inputs'] = {name: hashlib.sha256(getattr(args, name).read_bytes()).hexdigest()
                        for name in ('forecast', 'history')}
    report['historical'] = historical(args.history, rng)
    report['simulated'] = simulated(archive, rng)
    if args.second_forecast:
        second = Archive(args.second_forecast)
        report['inputs']['second_forecast'] = hashlib.sha256(args.second_forecast.read_bytes()).hexdigest()
        report['second_origin'] = dict(gws=second.gws, simulated=simulated(second, rng))
    (args.out/'results.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    write_figures(args.out, archive, line, test, mf, paths)


if __name__ == '__main__':
    main()
