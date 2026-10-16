#!/usr/bin/env python3
"""MM-only calibrated predictive minute distributions around frozen PR9 Model B.

No change to p,q,s,c, or expected minutes. Development chooses dispersion only
on 2024/25 GW14-21; all reported evaluation uses the identical PR9 holdout rows.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.special import logsumexp
from individual_mm_evidence import load_frame

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz'
OUT=ROOT/'analysis/results/mm-predictive-distribution-20261017'
ROLES=['regular','rotation_or_short_history','reserve']
CANDIDATES=[6.,10.,15.,22.,30.]
GRID=np.arange(1.,91.)
KEY=['season','fixture_uuid','player_uuid']

def conditional(mu,sigma,minimum=1):
    """Discrete bounded support 1..90 with exactly the supplied conditional mean.

    For starter minutes recorded as 0, duration support uses 1..90, so the
    p(start)*s identity remains within <1 minute only for s<1 (quarantined).
    """
    grid=np.arange(float(minimum),91.)\n    v=np.clip(np.asarray(mu,float),float(minimum),90.)
    z=-.5*((grid[None,:]-v[:,None])/float(sigma))**2
    lo=np.full(len(v),-8.)
    hi=np.full(len(v),8.)
    for _ in range(33):
        shift=(lo+hi)/2
        logits=z+shift[:,None]*GRID[None,:]
        probs=np.exp(logits-logsumexp(logits,axis=1,keepdims=True))
        means=(probs*grid[None,:]).sum(axis=1)
        low=means<v
        lo[low]=shift[low];hi[~low]=shift[~low]
    mid=(lo+hi)/2
    logits=z+mid[:,None]*GRID[None,:]
    probs=np.exp(logits-logsumexp(logits,axis=1,keepdims=True))
    return probs

def pred_masses(batch,starter_sigma,cameo_sigma):
    p=np.clip(batch.p.to_numpy(float),0,1)
    q=np.clip(batch.q.to_numpy(float),0,1)
    st=conditional(batch.s.to_numpy(float),starter_sigma,minimum=0)
    ca=conditional(batch.c.to_numpy(float),cameo_sigma,minimum=1)
    masses=p[:,None]*st\n    masses[:,1:]+=((1-p)*q)[:,None]*ca
    result=np.column_stack(((1-p)*(1-q),masses))
    if not np.allclose(result.sum(axis=1),1,atol=1e-7):raise ValueError('Not normalized')
    return result

def score(masses,actual):
    y=np.rint(actual).astype(int)
    y=np.clip(y,0,90)
    cdf=np.cumsum(masses,axis=1)
    crps=np.sum((cdf[:,:90]-(np.arange(90)[None,:]>=y[:,None]))**2,axis=1)
    z=masses[np.arange(len(y)),y]
    lower=np.argmax(cdf>=.1,axis=1)
    upper=np.argmax(cdf>=.9,axis=1)
    return crps,-np.log(np.clip(z,1e-12,1)),(y>=lower)&(y<=upper),lower,upper

def apply_one(g,starter_sigma,cameo_sigma):
    outputs=[]
    for start in range(0,len(g),512):
        chunk=g.iloc[start:start+512]
        mass=pred_masses(chunk,starter_sigma,cameo_sigma)
        crps,log,inside,l,u=score(mass,chunk.minutes.to_numpy(float))
        mean=mass@np.arange(91.)
        p0=mass[:,0]
        short=mass[:,1:16].sum(axis=1)
        medium=mass[:,16:61].sum(axis=1)
        long=mass[:,61:91].sum(axis=1)
        outputs.append(pd.DataFrame(dict(crps=crps,logloss=log,inside80=inside,lower80=l,upper80=u,mean=mean,p0=p0,p1_15=short,p16_60=medium,p61_90=long),index=chunk.index))
    return pd.concat(outputs).loc[g.index]

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    f=load_frame(SOURCE)
    f=f[f['mode']=='B'].copy()
    if f.duplicated(KEY).any():raise ValueError('Duplicated capsule forecasts')
    f['role']=f.prior_type.fillna('unknown')
    dev=f.season.eq('2024-25')&f.gw.between(14,21)
    evaluation=((f.season=='2024-25')&f.gw.between(22,38))|((f.season=='2025-26')&f.gw.between(6,38))
    if evaluation.sum()!=39264:raise ValueError('Evaluation mismatch: '+str(evaluation.sum()))
    if not dev.any():raise ValueError('No development forecasts; refuse to tune on evaluation')
    tune=[]
    chosen={}
    for role in ROLES:
        sample=f[dev&f.role.eq(role)].copy()
        if len(sample)<40:raise ValueError('Sparse dev role '+role+': '+str(len(sample)))
        for state in ['starter','cameo']:
            # Choose duration-dispersion in a strictly held-out model-selection period.
            trials=[]
            for sig in CANDIDATES:
                vals=apply_one(sample,sig,15.) if state=='starter' else apply_one(sample,15.,sig)
                crps=vals.crps.mean()
                trials.append((float(crps),sig))
                tune.append(dict(role=role,state=state,sigma=sig,development_crps=float(crps),n=len(sample)))
            chosen[(role,state)]=min(trials)[1]
    pd.DataFrame(tune).to_csv(OUT/'development_dispersion_selection.csv',index=False)
    rows=[];pred=[]
    for (season,role),g in f[evaluation].groupby(['season','role'],sort=True):
        if role not in ROLES:raise ValueError('Unknown role in eval: '+str(role))
        for model,ss,cs in [('homogeneous',15.,15.),('role_dependent',chosen[(role,'starter')],chosen[(role,'cameo')])]:
            res=apply_one(g,ss,cs)
            x=g[KEY+['team_id','gw','p','q','s','c','x','y','minutes']].copy().reset_index(drop=True)
            x['role']=role;x['mode']=model
            x=pd.concat([x,res.reset_index(drop=True)],axis=1)
            if np.max(np.abs(x['mean']-x['x']))>0.1:raise ValueError('Forecast expectation moved: '+str(np.max(np.abs(x['mean']-x['x']))))
            pred.append(x)
            rows.append(dict(model=model,season=season,role=role,n=len(g),crps=float(res.crps.mean()),logloss=float(res.logloss.mean()),coverage80=float(res.inside80.mean()),mean_interval_width=float((res.upper80-res.lower80).mean()),mae=float((g.x-g.minutes).abs().mean()),brier_start=float(np.mean((g.p-g.y)**2)),above60_errors=int(((g.x-g.minutes).abs()>60).sum()),mean_forecast_0=float(res.p0.mean()),actual_0=float((g.minutes==0).mean())))
    output=pd.concat(pred,ignore_index=True)
    output.to_csv(OUT/'distributions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    summary=pd.DataFrame(rows)
    summary.to_csv(OUT/'group_scores.csv',index=False)
    pooled=output.groupby('mode').agg(n=('crps','size'),crps=('crps','mean'),logloss=('logloss','mean'),coverage80=('inside80','mean'),mean_interval_width=('upper80','mean'),mae=('x',lambda x:np.nan)).reset_index().drop(columns='mae')
    pooled.to_csv(OUT/'pooled_scores.csv',index=False)
    all_bins=[]
    for (mode,role),g in output.groupby(['mode','role']):
        for name,prob,cond in [('0','p0',g.minutes.eq(0)),('1-15','p1_15',g.minutes.between(1,15)),('16-60','p16_60',g.minutes.between(16,60)),('61-90','p61_90',g.minutes.between(61,90))]:
            all_bins.append(dict(mode=mode,role=role,minutes_band=name,n=len(g),expected_probability=g[prob].mean(),realized_fraction=cond.mean(),absolute_calibration_error=abs(g[prob].mean()-cond.mean())))
    pd.DataFrame(all_bins).to_csv(OUT/'minute_band_calibration.csv',index=False)
    top=output[output['mode']=='role_dependent'].copy()
    top['ae']=(top.x-top.minutes).abs()
    top.sort_values('ae',ascending=False).head(200).to_csv(OUT/'top200_uncertain_cases.csv',index=False)
    doc=dict(scope='MM-only distribution model, original B p/q/s/c preserved',evaluation_rows=39264,train_scope='2024/25 GW14-21 only, role dispersion selected solely here',evaluated_seasons='2024/25 GW22-38; 2025/26 GW6-38',selected_sigma={r:{k:chosen[(r,k)]for k in ['starter','cameo']} for r in ROLES},limitations=['Outcome publication chronology uses inherited proxies','Historical research periods reused: not independent holdout','Starting duration permits 0 and cameo duration is positive','Conditional distribution shape is a candidate, not certified predictive coverage','Exact minute logloss uses rounded actual minutes; retained 0 minute events'],production_unchanged=True,point_models_untouched=True)
    (OUT/'summary.json').write_text(json.dumps(doc,indent=2)+'\n')
    print((OUT/'summary.json').read_text())
    print(summary.to_string(index=False))
    print(pd.read_csv(OUT/'pooled_scores.csv').to_string(index=False))
if __name__=='__main__':main()
