"""Serial offline survival-distribution sampler; original simulator is restored."""
from contextlib import contextmanager
import numpy as np
from . import joint_simulator

def distribution(hazard):
    h=np.asarray(hazard,float)
    if h.shape!=(90,) or not np.isfinite(h).all() or ((h<0)|(h>1)).any():raise ValueError('Invalid starter hazard')
    survival=np.cumprod(1-h);before=np.r_[1.,survival[:-1]]
    p=np.r_[before*h,survival[-1]]
    if not np.isclose(p.sum(),1):raise ValueError('Duration mass does not sum to one')
    return p

@contextmanager
def shadow_survival_sampler(hazards):
    saved=joint_simulator._sample_minutes
    distributions={str(pid):distribution(h) for pid,h in hazards.items() if h is not None}
    def sampler(rng,p):
        if p.player_id not in distributions:return saved(rng,p)
        if rng.random()<p.p_start:
            m=int(rng.choice(91,p=distributions[p.player_id]));return m,0,m
        if rng.random()<p.p_cameo_given_bench:
            m=int(np.clip(round(rng.normal(p.cameo_minutes_mean,7.)),1,45));return m,90-m,90
        return 0,90,90
    try:
        joint_simulator._sample_minutes=sampler
        yield
    finally:joint_simulator._sample_minutes=saved
