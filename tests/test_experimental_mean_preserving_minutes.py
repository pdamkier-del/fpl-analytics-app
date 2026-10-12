import numpy as np
import pytest
from fpl_v1_1_model.experimental_mean_preserving_minutes import (
    clipped_rounded_mean,normal_location,shadow_sampler,sample_minutes)
from fpl_v1_1_model import joint_simulator
from fpl_v1_1_model.joint_simulator import PlayerSimInput

@pytest.mark.parametrize('mean',[2.,7.,16.,45.,49.2,80.2773,88.9718,89.9])
@pytest.mark.parametrize('sigma',[7.,10.])
def test_inverse_preserves_exact_discrete_moment(mean,sigma):
    assert clipped_rounded_mean(normal_location(mean,sigma),sigma)==pytest.approx(mean,abs=1e-9)

def test_original_clipping_has_the_identified_bias():
    assert clipped_rounded_mean(90.,10.)==pytest.approx(86.01223941365,abs=.01)
    assert clipped_rounded_mean(49.2,7.,1,45)<45

def test_scope_restores_original_even_after_failure():
    original=joint_simulator._sample_minutes
    with pytest.raises(RuntimeError):
        with shadow_sampler():
            assert joint_simulator._sample_minutes is sample_minutes
            raise RuntimeError('interruption')
    assert joint_simulator._sample_minutes is original

@pytest.mark.parametrize('mean',[-1.,.5,91.,np.nan])
def test_never_substitutes_a_mean_for_invalid_inputs(mean):
    with pytest.raises(ValueError):normal_location(mean,10.)

def test_early_cameo_is_not_limited_to_45_or_relabelled_as_start():
    player=PlayerSimInput('test','A','MID',0.,1.,78.,90.)
    m,entry,end=sample_minutes(np.random.default_rng(1),player)
    assert m==90 and entry>0 and end==90
