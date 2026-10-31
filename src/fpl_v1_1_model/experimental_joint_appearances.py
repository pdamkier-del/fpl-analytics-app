"""Offline, partial repair: couple bench appearances under a shared sub budget.

This is NOT a physical timeline. Reported minute labels and conditional duration
laws remain untouched. Entry/exit pairing and three-window legality are not
established, so passing this experiment alone cannot authorize publication.
"""
from contextlib import contextmanager
from dataclasses import replace
import numpy as np

from .experimental_correctness_simulator import round_pair
from .experimental_physical_timeline import decompose_starts, _keeper_mass


def capped_probabilities(probabilities, capacity):
    """Preserve feasible marginals; proportional reduction only if infeasible.

    sum(q)>capacity proves no joint law with these conditional marginals exists.
    Reduction is an explicit candidate hypothesis, never a hidden correction.
    """
    q = np.asarray(probabilities, dtype=float)
    if (q.ndim != 1 or not np.isfinite(q).all() or ((q < 0) | (q > 1)).any()
            or not isinstance(capacity, int) or capacity < 0):
        raise ValueError('Invalid bench probabilities or capacity')
    total = float(q.sum())
    return q.copy() if total <= capacity else q * (capacity / total)


def sample_subset(probabilities, capacity, rng):
    q = capped_probabilities(probabilities, capacity)
    # One dummy rounds the total to an integer; discard it after dependent
    # rounding. The real count is floor/ceil(sum(q)), never above capacity.
    total = float(q.sum())
    target = min(capacity, int(np.ceil(total)))
    values = np.r_[q, max(0., target - total)]
    while True:
        free = np.flatnonzero((values > 0) & (values < 1))
        if len(free) < 2:
            break
        round_pair(values, int(free[0]), int(free[1]), rng)
    selected = values[:-1] > .5
    if selected.sum() > capacity:
        raise AssertionError('Shared substitution budget exceeded')
    return selected


class AppearanceKernel:
    def __init__(self, inp, role_distributions):
        from .joint_simulator import validate_joint_goalkeepers
        if not (inp.experimental_joint_starters and inp.experimental_joint_goalkeepers
                and inp.experimental_mean_preserving_minutes):
            raise ValueError('Existing joint B minute contract required')
        if (len({p.player_id for p in inp.players}) != len(inp.players)
                or inp.home_team == inp.away_team
                or any(p.team not in (inp.home_team, inp.away_team) for p in inp.players)):
            raise ValueError('Invalid player/team identity')
        self.input = inp
        self.teams = {}
        self.moments = {}
        self.diagnostics = []
        for team in (inp.home_team, inp.away_team):
            field = sorted((p for p in inp.players if p.team == team and not p.is_keeper),
                           key=lambda p: p.player_id)
            gks = tuple(p for p in inp.players if p.team == team and p.is_keeper)
            validate_joint_goalkeepers(gks, team, inp.verified_goalkeeper_roster_teams)
            ids = [p.player_id for p in field]
            given = role_distributions.get(team, role_distributions.get(str(team)))
            if given is None and str(team).isdigit():
                given = role_distributions.get(int(team))
            rows = ([(tuple(r.players), float(r.weight)) for r in given] if given
                    else decompose_starts(ids, [p.p_start for p in field]))
            if (not rows or any(len(s) != 10 or len(set(s)) != 10 or not set(s) <= set(ids)
                               or not np.isfinite(w) or w < 0 for s, w in rows)
                    or abs(sum(w for _, w in rows) - 1) > 1e-7):
                raise ValueError('Invalid role mixture')
            starts = np.array([sum(w for s, w in rows if uid in s) for uid in ids])
            if not np.allclose(starts, [p.p_start for p in field], atol=1e-6, rtol=0):
                raise ValueError('Role mixture changes MM start marginals')
            swap = float(sum(p.p_start * (1 - _keeper_mass(p)[90]) for p in gks))
            bench = np.zeros(len(field))
            infeasible = 0.
            reductions = 0.
            for selected, weight in rows:
                indices = [j for j, uid in enumerate(ids) if uid not in selected]
                q = np.array([field[j].p_cameo_given_bench for j in indices])
                for capacity, probability in [(5, 1 - swap), (4, swap)]:
                    effective = capped_probabilities(q, capacity)
                    mass = weight * probability
                    bench[indices] += mass * effective
                    infeasible += mass * (q.sum() > capacity + 1e-10)
                    reductions += mass * float((q - effective).sum())
            for j, p in enumerate(field):
                prob = float(starts[j])
                q = float(bench[j] / (1 - prob)) if prob < 1 - 1e-12 else 0.
                self.moments[p.player_id] = dict(p=prob, q=q, s=p.start_minutes_mean,
                    c=p.cameo_minutes_mean,
                    x=prob*p.start_minutes_mean + bench[j]*p.cameo_minutes_mean)
            self.diagnostics.append(dict(team=team, infeasible_lineup_probability=infeasible,
                                         expected_appearance_reduction=reductions))
            self.teams[team] = field, gks, rows

    def conditioned_input(self, inp, rng):
        from .joint_simulator import _weighted_choice
        if inp != self.input:
            raise ValueError('Appearance kernel belongs to different fixture inputs')
        updates = {}
        for team, (field, gks, rows) in self.teams.items():
            keeper = _weighted_choice(rng, gks, [p.p_start for p in gks])
            duration = int(rng.choice(91, p=_keeper_mass(keeper)))
            pmf = tuple(float(i == duration) for i in range(91))
            for p in gks:
                updates[p.player_id] = replace(p, p_start=float(p == keeper),
                    start_minutes_mean=float(duration) if p == keeper else p.start_minutes_mean,
                    goalkeeper_start_pmf=pmf if p == keeper else p.goalkeeper_start_pmf)
            selected, _ = rows[int(rng.choice(len(rows), p=[w for _, w in rows]))]
            bench = [p for p in field if p.player_id not in selected]
            chosen = sample_subset([p.p_cameo_given_bench for p in bench],
                                   4 if duration < 90 else 5, rng)
            cameos = {p.player_id for p, on in zip(bench, chosen) if on}
            for p in field:
                updates[p.player_id] = replace(p, p_start=float(p.player_id in selected),
                    p_cameo_given_bench=float(p.player_id in cameos))
        return replace(inp, players=tuple(updates[p.player_id] for p in inp.players),
                       experimental_joint_starters=False)


@contextmanager
def appearance_sampler(kernel):
    from . import joint_simulator as simulator
    original = simulator.simulate_match
    def sample(inp, rng, *, trace=None):
        return original(kernel.conditioned_input(inp, rng), rng, trace=trace)
    simulator.simulate_match = sample
    try:
        yield
    finally:
        simulator.simulate_match = original
