"""Defensive-contribution (DC) primitives for FPL v1.1.

2026/27 FPL awards two points to defenders at 10 CBIT and to midfielders/
forwards at 12 CBIRT.  Goalkeepers do not receive DC points.  The historical
count model can use a negative-binomial distribution because fixture DC counts
are materially overdispersed relative to Poisson.
"""
from __future__ import annotations
from math import exp,lgamma,log
from scipy.stats import nbinom,poisson


def threshold(position: str) -> int | None:
    if position == "DEF": return 10
    if position in ("MID","FWD"): return 12
    return None


def dc_points_from_count(position: str, count: int) -> int:
    t=threshold(position)
    return 2 if t is not None and int(count)>=t else 0


def threshold_probability(mu: float, position: str, dispersion_alpha: float=0.0) -> float:
    """P(DC count reaches the FPL threshold).

    ``dispersion_alpha`` is NB2 alpha where Var(Y)=mu+alpha*mu^2. alpha=0
    reduces to Poisson.
    """
    if mu < 0 or dispersion_alpha < 0:
        raise ValueError("mu and dispersion_alpha must be non-negative")
    t=threshold(position)
    if t is None or mu<=0: return 0.0
    if dispersion_alpha <= 1e-12:
        return float(poisson.sf(t-1,mu))
    r=1.0/dispersion_alpha
    p=r/(r+mu)
    return float(nbinom.sf(t-1,r,p))


def expected_points(mu: float, position: str, dispersion_alpha: float=0.0) -> float:
    return 2.0*threshold_probability(mu,position,dispersion_alpha)


def nb2_logpmf(y: int, mu: float, alpha: float) -> float:
    """NB2 log-PMF, with a Poisson limit for alpha≈0."""
    if y < 0 or mu < 0 or alpha < 0:
        raise ValueError("invalid NB2 input")
    if mu <= 0: return 0.0 if y==0 else -1e12
    if alpha <= 1e-10:
        return y*log(mu)-mu-lgamma(y+1)
    r=1.0/alpha; p=r/(r+mu)
    return lgamma(y+r)-lgamma(r)-lgamma(y+1)+r*log(p)+y*log(1-p)
