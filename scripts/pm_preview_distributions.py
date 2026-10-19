"""Public preview summaries from exact seeded PM replay; locked PM is untouched.

Replay uses the same match sampler and seed as the aggregate, with no extra RNG
calls inside a match. The second pass trades computation for a strict immutable
production boundary. These are empirical predictive distributions, not estimates
of parameter uncertainty or independently certified calibration.
"""
import numpy as np
from fpl_v1_1_model import joint_simulator as simulator


def simulate_with_distributions(inp, *, n=400, seed=93000000):
    aggregate=simulator.simulate_many(inp,n=n,seed=seed)
    rng=np.random.default_rng(seed)
    draws={p.player_id:[] for p in inp.players}
    for _ in range(n):
        result=simulator.simulate_match(inp,rng)
        for pid in draws:
            r=result[pid]
            draws[pid].append((r.minutes,r.started,r.points))
    for pid,values in draws.items():
        minutes,started,points=np.asarray(values).T
        row=aggregate[pid]
        if float(points.mean())!=row['xPts'] or float(minutes.mean())!=row['expected_minutes']:
            raise ValueError('Preview distributions do not reproduce locked PM draws')
        row['distribution']={
            'draws':n,'p_start':float(started.mean()),
            'p_zero':float(np.mean(minutes==0)),
            'p_cameo':float(np.mean((minutes>0)&(started==0))),
            'p_60_plus':float(np.mean(minutes>=60)),'p_90':float(np.mean(minutes==90)),
            'minute_bins':[float(np.mean(minutes==0)),float(np.mean((minutes>0)&(minutes<60))),float(np.mean((minutes>=60)&(minutes<90))),float(np.mean(minutes==90))],
            'p_2_plus':float(np.mean(points>=2)),'p_5_plus':float(np.mean(points>=5)),'p_10_plus':float(np.mean(points>=10)),
            'points_interval80':[float(np.quantile(points,.1)),float(np.quantile(points,.9))],
            'pm_expected_minutes':float(minutes.mean())}
    return aggregate
