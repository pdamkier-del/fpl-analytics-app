"""Offline extra-difficulty and individual chance-quality response tests."""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logit
from .experimental_shot_finishing import fit_shots


@dataclass
class DifficultyFit:
    intercept: float
    slope: float
    offsets: dict
    shapes: dict

    def predict(self, xg, players):
        x=np.asarray(xg,dtype=float)
        if not np.isfinite(x).all() or ((x<0)|(x>1)).any():raise ValueError('Invalid xG')
        u=np.array([self.offsets.get(str(p),0.) for p in players])
        v=np.array([self.shapes.get(str(p),0.) for p in players])
        return expit(self.intercept+self.slope*np.exp(-v)*logit(np.clip(x,1e-6,1-1e-6))+u)


def fit_difficulty(frame,cutoff,*,ridge=5.,shape_ridge=None,power=0.):
    # Reuse the baseline's temporal/data validation and a stable warm start.
    baseline=fit_shots(frame,cutoff,ridge=ridge)
    if shape_ridge is not None and (not np.isfinite(shape_ridge) or shape_ridge<=0):
        raise ValueError('Invalid shape prior')
    if not np.isfinite(power) or power<0:raise ValueError('Invalid difficulty weighting')
    if shape_ridge is None and power==0:
        return DifficultyFit(baseline.intercept,baseline.slope,baseline.offsets,{})
    ids,index=np.unique(frame.player_uuid.astype(str),return_inverse=True);n=len(ids)
    x=frame.xg.to_numpy(dtype=float);y=frame.goal.to_numpy(dtype=float)
    z=logit(np.clip(x,1e-6,1-1e-6))
    w=np.clip((.2/np.maximum(x,.01))**power,.5,4.);w/=w.mean()
    shape=shape_ridge is not None

    def objective(beta):
        u=beta[2:2+n]
        v=beta[2+n:] if shape else np.zeros(n)
        ez=np.exp(-v[index])*z
        eta=beta[0]+beta[1]*ez+u[index]
        residual=w*(expit(eta)-y)
        loss=np.sum(w*(np.logaddexp(0.,eta)-y*eta))+.5*ridge*np.sum(u*u)
        grad=np.r_[residual.sum(),residual@ez,
                   np.bincount(index,weights=residual,minlength=n)+ridge*u]
        if shape:
            loss+=.5*shape_ridge*np.sum(v*v)
            grad=np.r_[grad,np.bincount(index,weights=-residual*beta[1]*ez,minlength=n)+shape_ridge*v]
        return float(loss),grad

    initial=np.r_[baseline.intercept,baseline.slope,[baseline.offsets[p] for p in ids],np.zeros(n) if shape else []]
    result=minimize(objective,initial,jac=True,method='L-BFGS-B',
                    bounds=[(-5.,5.),(.1,3.)]+[(None,None)]*n+([(-1.,1.)]*n if shape else []),
                    options={'maxiter':700,'ftol':1e-11,'gtol':1e-6})
    if not result.success:raise ValueError('Difficulty fit failed: '+str(result.message))
    return DifficultyFit(float(result.x[0]),float(result.x[1]),
                         dict(zip(ids,map(float,result.x[2:2+n]))),
                         dict(zip(ids,map(float,result.x[2+n:]))) if shape else {})
