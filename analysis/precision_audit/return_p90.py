"""Isolated substitution-priority hypothesis. Never imported by the app.

The return flag is the existing predeadline episode proxy (medical OR
suspension); it is not medical clearance. Parameters are hypotheses, not fitted
coefficients. No target outcome is accepted by this kernel.
"""
from dataclasses import replace
import numpy as np
from fpl_v1_1_model.experimental_physical_timeline import PhysicalKernel, _states, _keeper_mass
from fpl_v1_1_model.experimental_joint_role_assignment import RoleLineup


def tilt_return_starts(inp, dist, returning, *, log_odds=.5):
    """Reweight legal XIs, bounded by existing player availability ceilings.

    This is a separate fixed hypothesis for the negative returning start bias
    in PR29. Preserve each original p(play) ceiling while changing p(start).
    Never manufacture an independent eleventh outfield starter.
    """
    if not np.isfinite(log_odds) or not 0 <= log_odds <= 1:
        raise ValueError('Return log odds must be in [0, 1]')
    returning = frozenset(returning)
    known = {p.player_id for p in inp.players if not p.is_keeper}
    if not returning <= known:
        raise ValueError('Unknown or goalkeeper return identity')
    if log_odds == 0 or not returning:
        return inp, dist
    kernel = PhysicalKernel(inp, dist)
    new_dist = {}
    changed = {}
    for team, data in kernel.teams.items():
        ids = [p.player_id for p in data['field']]
        # Retain actual formation/role metadata when available.
        given = dist.get(team, dist.get(str(team))) if dist else None
        if given is None and str(team).isdigit() and dist:
            given = dist.get(int(team))
        source = list(given) if given else [
            RoleLineup(formation='audit-convex-XI', players=selected, roles=tuple('unknown' for _ in selected), weight=w)
            for selected, w in data['weights'].items()]
        w = np.array([r.weight for r in source], float)
        count = np.array([len(returning.intersection(r.players)) for r in source])
        target = w*np.exp(log_odds*count)
        target /= target.sum()
        indicator = np.array([[uid in r.players for uid in ids] for r in source], float)
        old = w @ indicator
        desired = target @ indicator
        ceilings = np.array([p.p_start+(1-p.p_start)*p.p_cameo_given_bench for p in data['field']])
        positive = desired-old > 1e-12
        alpha = min(1., max(0., float(np.min((ceilings[positive]-old[positive]) /
                                           (desired[positive]-old[positive]))))) if positive.any() else 1.
        weights = (1-alpha)*w+alpha*target
        marginals = weights @ indicator
        new_dist[team] = [replace(r, weight=float(v)) for r, v in zip(source, weights)]
        for j, p in enumerate(data['field']):
            start = float(np.clip(marginals[j], 0, 1))
            q = float(np.clip((ceilings[j]-start)/(1-start), 0, 1)) if start < 1-1e-12 else 0.
            changed[p.player_id] = replace(p, p_start=start, p_cameo_given_bench=q)
    return replace(inp, players=tuple(changed.get(p.player_id, p) for p in inp.players)), new_dist


class ReturnP90Kernel(PhysicalKernel):
    def __init__(self, inp, dist=None, *, returning=(), return_scale=0.5,
                 regular_floor=2.0, states=128):
        if not np.isfinite(return_scale) or not 0 < return_scale <= 1:
            raise ValueError('Return scale must be in (0, 1]')
        if not np.isfinite(regular_floor) or not 0 <= regular_floor <= 10:
            raise ValueError('Regular exit floor must be in [0, 10]')
        returning = frozenset(returning)
        if not returning <= {p.player_id for p in inp.players if not p.is_keeper}:
            raise ValueError('Unknown or goalkeeper return identity')
        super().__init__(inp, dist, states=states)
        self.audit.update(candidate='return-p90-exit-priority-v1',
                          return_scale=return_scale, regular_floor=regular_floor)
        for data in self.teams.values():
            field, weights = data['field'], data['weights']
            adjusted = []
            for p in field:
                loss = max(0., 90 - p.start_minutes_mean)
                if p.player_id in returning:
                    loss *= return_scale
                elif p.p_start >= .9 and loss < regular_floor:
                    loss = regular_floor
                adjusted.append(replace(p, start_minutes_mean=90-loss))
            swap = sum(p.p_start*(1-_keeper_mass(p)[90]) for p in data['keepers'])
            pmf = np.zeros((len(field), 91))
            start_total = np.zeros(len(field))
            for selected, weight in sorted(weights.items()):
                for changed, prob in [(False, 1-swap), (True, swap)]:
                    if prob <= 1e-14:
                        continue
                    minutes, start = _states(adjusted, selected, 4 if changed else 5,
                                             2 if changed else 3, states)
                    data['ensembles'][selected, changed] = minutes, start
                    start_total += weight*prob*minutes.mean(axis=0)*start
                    for j in range(len(field)):
                        pmf[j] += weight*prob*np.bincount(minutes[:, j], minlength=91)/states
            for j, p in enumerate(field):
                old = self.moments[p.player_id]
                mean = float(pmf[j] @ np.arange(91))
                play = float(1-pmf[j, 0])
                s = float(start_total[j]/old['p']) if old['p'] else p.start_minutes_mean
                bench = max(0., play-old['p'])
                c = (mean-start_total[j])/bench if bench > 1e-12 else p.cameo_minutes_mean
                self.moments[p.player_id] = dict(
                    p=old['p'], q=bench/(1-old['p']) if old['p'] < 1-1e-12 else 0.,
                    s=s, c=float(c), x=mean, p_play=play,
                    p60=float(pmf[j, 60:].sum()), p90=float(pmf[j, 90]), pmf=pmf[j].tolist())
            if abs(sum(self.moments[p.player_id]['x'] for p in field)-900) > 1e-6:
                raise AssertionError('Candidate lost physical minutes')
