"""Opt-in shadow sampler: conditional means are moments, not Normal locations.

The production sampler and its locked coefficients remain unchanged. Both
appearance states use the physical 1..90 minute support. An early substitute
can play more than 45 minutes; mean-preservation is impossible on 1..45 when
the supplied conditional mean exceeds 45. No player IDs or fitted parameters.
"""
from contextlib import contextmanager
from functools import lru_cache
import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr


def clipped_rounded_mean(location, sigma, low=1, high=90):
    if sigma <= 0 or low >= high:
        raise ValueError('Invalid distribution support or scale')
    # E[Y] = low + sum_{k=low}^{high-1} P(Y > k), for integer Y.
    thresholds=np.arange(low,high,dtype=float)+.5
    return float(low+ndtr((float(location)-thresholds)/sigma).sum())


@lru_cache(maxsize=100000)
def normal_location(mean, sigma, low=1, high=90):
    mean=float(mean)
    if not np.isfinite(mean) or mean<low-1e-10 or mean>high+1e-10:
        raise ValueError('Conditional mean outside the physical support')
    mean=float(np.clip(mean,low,high))
    if mean==low or mean==high:return mean
    return float(brentq(lambda location:clipped_rounded_mean(location,sigma,low,high)-mean,
                       low-12*sigma,high+12*sigma,xtol=1e-12))


def draw_duration(rng, mean, sigma):
    location=normal_location(float(mean),sigma)
    noise=rng.normal(location,sigma) # Keep the original random draw count.
    if mean<=1:return 1
    if mean>=90:return 90
    return int(np.clip(round(noise),1,90))


def sample_minutes(rng,p):
    if rng.random()<p.p_start:
        m=draw_duration(rng,p.start_minutes_mean,10.)
        return m,0,m
    if rng.random()<p.p_cameo_given_bench:
        m=draw_duration(rng,p.cameo_minutes_mean,7.)
        # Retain the non-start flag even if minute rounding produces 90.
        entry=90-m if m<90 else np.nextafter(0.,1.)
        return m,entry,90
    return 0,90,90


@contextmanager
def shadow_sampler():
    """Single-process experimental scope; restoration is exception-safe."""
    from . import joint_simulator
    original=joint_simulator._sample_minutes
    joint_simulator._sample_minutes=sample_minutes
    try:yield
    finally:joint_simulator._sample_minutes=original
