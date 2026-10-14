"""Offline component candidates only; no production imports or parameter changes."""
import numpy as np
import pandas as pd
from scipy.special import expit,logit
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler,OneHotEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

NUMERIC=['baseline_logit','start_share6','last_started','start_streak','history_n','days_since_play','team_rest_days','minutes_14d','start_history_mean']

def start_inputs(f):
    x=f.copy();x['baseline_logit']=logit(np.clip(x.new_p_start,1e-6,1-1e-6))
    x['history_n']=np.minimum(x.history_n,38)
    x['start_streak']=np.minimum(x.start_streak,12)
    x['days_since_play']=np.minimum(x.days_since_play,60)
    x['team_rest_days']=np.minimum(x.team_rest_days,30)
    if not np.isfinite(x[NUMERIC].to_numpy()).all():raise ValueError('Invalid pre-cutoff feature')
    return x

def fit_start(train,target,C=1.,hierarchical=False):
    """L2 partial-pooling logistic model, not a fitted Bayesian variance hierarchy."""
    if 'outcome_known_at' in train and 'cutoff' in target:
        known=pd.to_datetime(train.outcome_known_at,utc=True,format='mixed')
        if (known>=pd.to_datetime(target.cutoff,utc=True).min()).any():raise ValueError('Future outcome in start fit')
    if len(train)<500 or train.y.nunique()<2:return target.new_p_start.to_numpy()
    categories=['pos']+(['player_uuid','team_id'] if hierarchical else [])
    pre=ColumnTransformer([('continuous',StandardScaler(),NUMERIC),('categories',OneHotEncoder(handle_unknown='ignore'),categories)])
    model=make_pipeline(pre,LogisticRegression(C=C,max_iter=1000,solver='lbfgs',tol=1e-7))
    model.fit(start_inputs(train),train.y)
    p=model.predict_proba(start_inputs(target))[:,1]
    # Retain baseline hard endpoints; historical medical caps are not inferred.
    p=np.where(target.new_p_start.eq(0),0,np.where(target.new_p_start.eq(1),1,p))
    return project_partition(target,p)

def project_partition(frame,p):
    """Exactly one expected GK and ten outfield starters; hard zero/one preserved."""
    p=np.asarray(p,float).copy()
    if not np.isfinite(p).all() or ((p<0)|(p>1)).any():raise ValueError('Invalid probability')
    for indices in frame.groupby(['fixture_uuid','team_id'],sort=False).indices.values():
        indices=np.asarray(indices)
        for isgk,count in [(True,1),(False,10)]:
            idx=indices[frame.iloc[indices].pos.isin(['GK','GKP']).to_numpy()==isgk]
            vals=p[idx];caps=frame.iloc[idx].team_news_availability_cap.to_numpy() if 'team_news_availability_cap' in frame else np.ones(len(idx))
            vals=np.minimum(vals,caps);fixed=vals>=1.;mutable=(vals>0)&(vals<1);need=count-int(fixed.sum())
            if need<0 or need>caps[mutable].sum()+1e-9:raise ValueError('Infeasible roster partition')
            if need==0:vals[mutable]=0.
            elif abs(need-caps[mutable].sum())<1e-9:vals[mutable]=caps[mutable]
            else:
                z=logit(vals[mutable]);lo,hi=-60.,60.
                for _ in range(90):
                    mid=(lo+hi)/2
                    if np.minimum(caps[mutable],expit(z+mid)).sum()<need:lo=mid
                    else:hi=mid
                vals[mutable]=np.minimum(caps[mutable],expit(z+(lo+hi)/2))
            p[idx]=vals
    return p

def empirical_hazard(minutes,weights=None):
    """T<90 is an all-cause exit; T=90 is right censored at match completion."""
    t=np.asarray(minutes,float)
    if not np.isfinite(t).all() or ((t<0)|(t>90)).any():raise ValueError('Invalid duration')
    w=np.ones(len(t)) if weights is None else np.asarray(weights,float)
    if len(w)!=len(t) or (w<0).any() or not np.isfinite(w).all():raise ValueError('Invalid weights')
    # Official FPL minutes are integer observations, not fabricated exit timestamps.
    if not np.allclose(t,np.round(t)):raise ValueError('Fractional exit time cannot be inferred from FPL minutes')
    hist=np.bincount(t.astype(int),weights=w,minlength=91)
    risk=np.cumsum(hist[::-1])[::-1][:90];events=hist[:90]
    return np.divide(events,risk,out=np.zeros(90),where=risk>0),risk,events

def hazard_mean(h):
    h=np.asarray(h,float)
    if h.shape!=(90,) or not np.isfinite(h).all() or ((h<0)|(h>1)).any():raise ValueError('Invalid hazard')
    return float(np.cumprod(1-h).sum())

def survival_prediction(target,observations,prior_started,half_days=21.,strength=2.):
    """Pre-kickoff pooled hazard; no realized target score, coach or injury proxy."""
    cut=pd.to_datetime(target.cutoff,utc=True).min()
    past=observations[(observations.known<cut)&observations.started.eq(1)]
    pool=prior_started.copy()
    # The caller supplies only strictly cutoff-known training rows.
    if len(pool) and not (pd.to_datetime(pool['known'],utc=True)<cut).all():raise ValueError('Future outcome in survival prior')
    priors={}
    for pos,g in pool.groupby('pos'):
        priors[str(pos)]=empirical_hazard(g.minutes.to_numpy())[0]
    history={str(pid):g for pid,g in past.groupby('player_uuid')}
    result=[]
    for r in target.itertuples():
        h0=priors.get(str(r.pos))
        if h0 is None:result.append(float(r.new_start_minutes));continue
        hist=history.get(str(r.player_uuid))
        if hist is None:h=h0
        else:
            age=(cut-hist.known).dt.total_seconds().to_numpy()/86400
            w=np.exp2(-age/half_days);_,risk,events=empirical_hazard(hist.minutes.to_numpy(),w)
            h=(events+strength*h0)/(risk+strength)
        result.append(hazard_mean(h))
    return np.asarray(result)
