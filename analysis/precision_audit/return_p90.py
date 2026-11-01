"""Isolated substitution-priority hypothesis. Never imported by the app.

The return flag is the existing predeadline episode proxy (medical OR
suspension); it is not medical clearance. Parameters are hypotheses, not fitted
coefficients. No target outcome is accepted by this kernel.
"""
from dataclasses import replace
import numpy as np
from fpl_v1_1_model.experimental_physical_timeline import PhysicalKernel, _states, _keeper_mass


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
