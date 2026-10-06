"""Project exact-11 P(start) onto cutoff-safe availability caps."""
from __future__ import annotations
import numpy as np
from scipy.special import expit,logit
from scipy.optimize import brentq

def project_exact_starters_with_caps(frame,raw_p,caps,*,starters=11):
    """Per fixture/team exact starter projection with player upper bounds.

    The ranking signal comes from raw_p. Availability only imposes caps. Removed
    probability mass is redistributed monotonically over the remaining roster.
    """
    p=np.asarray(raw_p,dtype=float)
    cap=np.clip(np.asarray(caps,dtype=float),0.0,1.0)
    if len(p)!=len(frame) or len(cap)!=len(frame):
        raise ValueError("length mismatch")
    out=np.zeros_like(p)
    for idxs in frame.groupby(["fixture_uuid","team_id"],sort=False).indices.values():
        idxs=np.asarray(idxs,dtype=int)
        pp=np.clip(p[idxs],1e-8,1-1e-8)
        cc=cap[idxs]
        need=float(starters)
        if cc.sum()+1e-9<need:
            raise ValueError(f"infeasible availability caps: need {need}, cap sum {cc.sum():.6f}")
        z=logit(pp)
        def total(shift):
            return np.minimum(cc,expit(z+shift)).sum()
        lo,hi=-60.0,60.0
        if total(lo)>need+1e-9 or total(hi)<need-1e-9:
            raise ValueError("cannot bracket exact-starter projection")
        shift=brentq(lambda b: total(b)-need,lo,hi)
        vals=np.minimum(cc,expit(z+shift))
        # tiny numerical correction among uncapped players
        diff=need-vals.sum()
        if abs(diff)>1e-8:
            free=np.where(vals<cc-1e-8)[0]
            if len(free):
                vals[free]+=diff/len(free)
        if abs(vals.sum()-need)>1e-6:
            raise ValueError("exact starter projection failed")
        if np.any(vals>cc+1e-7):
            raise ValueError("availability cap violated")
        out[idxs]=vals
    return out
