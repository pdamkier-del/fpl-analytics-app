"""Proper scores reused from PR41/43 definitions; no model fitting."""
import hashlib
import math
import statistics
import numpy as np

EPS=1e-6


def probability(p):
    if isinstance(p,bool) or not isinstance(p,(int,float)) or not math.isfinite(p) or not 0<=p<=1:
        raise ValueError('Probability outside [0,1]')
    return float(p)


def bernoulli(p,y):
    p=probability(p)
    if y not in (0,1,False,True):raise ValueError('Binary target required')
    q=min(1-EPS,max(EPS,p))
    return dict(brier=(p-y)**2,log_loss=-(y*math.log(q)+(1-y)*math.log1p(-q)))


def crps(samples,y):
    # PR41/43 empirical-law CRPS, not a regenerated or Gaussian distribution.
    x=np.sort(np.asarray(samples,float));n=len(x)
    if n<2 or not np.isfinite(x).all()or not math.isfinite(y):raise ValueError('Invalid empirical law')
    return float(np.mean(abs(x-y))-np.sum((2*np.arange(1,n+1)-n-1)*x)/n**2)


def law_summary(samples,y,key):
    x=np.asarray(samples,float)
    result={'crps':crps(x,y),'haul':{str(k):dict(p=float(np.mean(x>=k)),y=int(y>=k),**bernoulli(float(np.mean(x>=k)),int(y>=k)))for k in [2,5,10]}}
    u=int(hashlib.sha256(('2026112304:'+key).encode()).hexdigest()[:16],16)/2**64
    result['randomized_pit']=float(np.mean(x<y)+u*np.mean(x==y))
    result['intervals']={}
    for level in [.5,.8,.95]:
        low,high=np.quantile(x,[(1-level)/2,(1+level)/2],method='inverted_cdf')
        result['intervals'][str(level)]=dict(low=float(low),high=float(high),width=float(high-low),
            forecast_mass=float(np.mean((x>=low)&(x<=high))),covered=bool(low<=y<=high))
    return result


def calibration(pairs):
    bins=[dict(low=i/10,high=(i+1)/10,count=0,predicted_sum=0.,observed_sum=0.)for i in range(10)]
    for p,y in pairs:
        p=probability(p);b=bins[min(9,int(p*10))];b['count']+=1;b['predicted_sum']+=p;b['observed_sum']+=y
    for b in bins:
        b['predicted_mean']=b['predicted_sum']/b['count']if b['count']else None
        b['observed_mean']=b['observed_sum']/b['count']if b['count']else None
    return bins


def error_summary(pairs):
    errors=[p-y for p,y in pairs]
    if not errors:return dict(n=0,mae=None,mse=None,rmse=None,bias=None)
    mse=statistics.mean(e*e for e in errors)
    return dict(n=len(errors),mae=statistics.mean(abs(e)for e in errors),mse=mse,
                rmse=math.sqrt(mse),bias=statistics.mean(errors))


def block_intervals(values,fixtures,*,locked=False):
    """Whole-GW paired values; no inference before the registered final gate."""
    x=np.asarray([np.nan if v is None else v for v in values],float);n=int(np.isfinite(x).sum())
    if not locked or n<12 or fixtures<120:
        return dict(status='not_inferential',reason='Final lock and12GW/120fixture gates required',gws=n,calendar_origins=len(x),fixtures=fixtures)
    result=dict(status='final_descriptive_bootstrap',gws=n,calendar_origins=len(x),mean=float(np.nanmean(x)),blocks={})
    for length in [3,6]:
        rng=np.random.default_rng(2026112304);draw=[];attempts=0
        while len(draw)<2000 and attempts<4000:
            attempts+=1
            starts=rng.integers(0,len(x),size=math.ceil(len(x)/length))
            indices=[(int(s)+j)%len(x)for s in starts for j in range(length)][:len(x)]
            sampled=x[indices]
            if np.isfinite(sampled).any():draw.append(float(np.nanmean(sampled)))
        if len(draw)!=2000:raise ValueError('Insufficient supported GW-block resamples; no invented interval')
        result['blocks'][str(length)]={'ci95':np.quantile(draw,[.025,.975]).tolist(),
                                     'family_ci97_5':np.quantile(draw,[.0125,.9875]).tolist()}
    return result
