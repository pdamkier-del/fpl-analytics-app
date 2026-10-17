import numpy as np
import pytest
from fpl_v1_1_model import joint_simulator as js
from fpl_v1_1_model.experimental_mm_research import empirical_hazard,hazard_mean
from fpl_v1_1_model.experimental_survival_sampler import distribution,shadow_survival_sampler

def test_duration_mass_and_exact_mean_preserve_completion():
    t=np.array([45,60,79,90,90]);h=empirical_hazard(t)[0];p=distribution(h)
    assert np.isclose(p.sum(),1)
    assert np.isclose(p@np.arange(91),hazard_mean(h))
    assert np.isclose(p[90],.4)

def test_serial_sampler_restores_original_and_preserves_nonstart_branch():
    old=js._sample_minutes;p=js.PlayerSimInput('p','t','FWD',1.,0.,70.,15.)
    h=empirical_hazard([60,90,90])[0]
    with pytest.raises(RuntimeError):
        with shadow_survival_sampler({'p':h.tolist()}):
            rng=np.random.default_rng(10);draw=np.array([js._sample_minutes(rng,p)[0] for _ in range(6000)])
            assert abs(draw.mean()-80)<.6
            raise RuntimeError('restore')
    assert js._sample_minutes is old

def test_missing_hazard_is_draw_for_draw_original_and_invalid_rejected():
    p=js.PlayerSimInput('p','t','FWD',.8,.3,83.,15.);r1=np.random.default_rng(3);r2=np.random.default_rng(3)
    a=[js._sample_minutes(r1,p) for _ in range(100)]
    with shadow_survival_sampler({'p':None}):b=[js._sample_minutes(r2,p) for _ in range(100)]
    assert a==b
    with pytest.raises(ValueError):distribution(np.ones(90)*1.1)
