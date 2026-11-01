"""Offline conditional shot conversion; never imported by production PM."""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logit


@dataclass
class ShotFit:
    intercept: float
    slope: float
    offsets: dict

    def predict(self, xg, players):
        x = np.asarray(xg, dtype=float)
        if not np.isfinite(x).all() or ((x < 0) | (x > 1)).any():
            raise ValueError('Invalid pre-shot xG')
        return expit(self.intercept + self.slope * logit(np.clip(x, 1e-6, 1-1e-6))
                     + np.array([self.offsets.get(str(p), 0.) for p in players]))


def fit_shots(frame, cutoff, *, ridge=None, half_life=None):
    """Gaussian partial pooling around a shared source-calibration curve.

    Only pre-shot xG and stable player identity are predictors. The target is
    binary goal outcome; post-shot xGOT and placement are intentionally unused.
    """
    import pandas as pd
    cut = pd.Timestamp(cutoff)
    known = pd.to_datetime(frame.known, utc=True)
    if cut.tzinfo is None or known.isna().any() or not known.lt(cut).all():
        raise ValueError('Training observations must be known before cutoff')
    if frame.empty:
        raise ValueError('No prior shots')
    x = frame.xg.to_numpy(dtype=float)
    y = frame.goal.to_numpy(dtype=float)
    if not np.isfinite(x+y).all() or ((x < 0) | (x > 1)).any() or not np.isin(y, [0.,1.]).all():
        raise ValueError('Invalid native shot observations')
    if ridge is not None and (not np.isfinite(ridge) or ridge <= 0):
        raise ValueError('Invalid player prior strength')
    if half_life is not None and (not np.isfinite(half_life) or half_life <= 0):
        raise ValueError('Invalid recency')
    ids, index = np.unique(frame.player_uuid.astype(str), return_inverse=True)
    z = logit(np.clip(x, 1e-6, 1-1e-6))
    weights = (np.ones(len(frame)) if half_life is None else
               np.exp2(-(cut-known).dt.total_seconds().to_numpy()/86400/half_life))
    count = len(ids) if ridge is not None else 0

    def objective(beta):
        eta = beta[0] + beta[1]*z
        if count:
            eta += beta[2:][index]
        residual = weights*(expit(eta)-y)
        loss = np.sum(weights*(np.logaddexp(0.,eta)-y*eta))
        grad = [residual.sum(), residual@z]
        if count:
            loss += .5*ridge*np.sum(beta[2:]**2)
            grad = np.r_[grad, np.bincount(index, weights=residual, minlength=count)+ridge*beta[2:]]
        return float(loss), np.asarray(grad)

    start = np.zeros(2+count)
    start[1] = 1.
    result = minimize(objective, start, method='L-BFGS-B', jac=True,
                      bounds=[(-5.,5.),(.1,3.)]+[(None,None)]*count,
                      options={'maxiter':500,'ftol':1e-11,'gtol':1e-6})
    if not result.success:
        raise ValueError('Shot model fit failed: '+str(result.message))
    return ShotFit(float(result.x[0]), float(result.x[1]),
                   dict(zip(ids, map(float,result.x[2:]))) if count else {})
