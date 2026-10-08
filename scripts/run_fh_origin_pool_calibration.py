#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd

def load_origin(root:Path,prefix:str,origin:int):
    p=root/f'{prefix}{origin}'/'tc_candidates.csv'
    if not p.exists(): return None
    z=pd.read_csv(p)
    z['origin_gw']=int(origin)
    z['horizon']=z.gw.astype(int)-int(origin)
    return z

def panel(root,prefix,start=6,end=38,seed=20261008):
    origins=list(range(start,end+1))
    rng=np.random.default_rng(seed);rng.shuffle(origins)
    rows=[];order=[]
    for rank,o in enumerate(origins):
        z=load_origin(Path(root),prefix,o)
        if z is None: continue
        z['random_order']=rank;rows.append(z);order.append(int(o))
    if not rows: raise ValueError('no origin files')
    return pd.concat(rows,ignore_index=True),order

def matched_reliability(p):
    # Near-deadline reference: origin==target GW for the same player.
    ref=(p[p.horizon.eq(0)][['gw','candidate_id','mean_points']]
         .rename(columns={'mean_points':'ref_mean'}).drop_duplicates(['gw','candidate_id']))
    x=p.merge(ref,on=['gw','candidate_id'],how='inner')
    x=x[x.horizon.ge(0)].copy()
    rows=[]
    for k,g in x.groupby('horizon',sort=True):
        if len(g)<20: continue
        a=g.mean_points.astype(float);b=g.ref_mean.astype(float)
        pear=float(a.corr(b,method='pearson')) if a.std()>1e-9 and b.std()>1e-9 else np.nan
        spear=float(a.corr(b,method='spearman')) if a.std()>1e-9 and b.std()>1e-9 else np.nan
        rel=float(np.sqrt(max(0.,pear)*max(0.,spear))) if np.isfinite(pear) and np.isfinite(spear) else np.nan
        rows.append(dict(horizon=int(k),n=int(len(g)),pearson=pear,spearman=spear,
                         reliability=rel,mae=float(np.mean(np.abs(a-b))),
                         rmse=float(np.sqrt(np.mean((a-b)**2)))))
    return pd.DataFrame(rows),x

def fit_rho(m):
    z=m[(m.horizon>0)&m.reliability.notna()].copy()
    if z.empty: raise ValueError('no nonzero horizons')
    k=z.horizon.to_numpy(float);r=np.clip(z.reliability.to_numpy(float),1e-6,1.)
    log_rho=float(np.sum(k*np.log(r))/np.sum(k*k))
    rho=float(np.exp(log_rho));pred=np.power(rho,k)
    return rho,float(np.sqrt(np.mean((pred-r)**2)))

def bootstrap(joined,n,seed):
    rng=np.random.default_rng(seed+1);vals=[]
    gws=np.array(sorted(joined.gw.unique()),int)
    for _ in range(int(n)):
        draw=rng.choice(gws,size=len(gws),replace=True);parts=[]
        for j,gw in enumerate(draw):
            q=joined[joined.gw.eq(int(gw))].copy();q['_b']=j;parts.append(q)
        b=pd.concat(parts,ignore_index=True);rows=[]
        for k,g in b.groupby('horizon'):
            if int(k)==0 or len(g)<20: continue
            a=g.mean_points.astype(float);r=g.ref_mean.astype(float)
            if a.std()<=1e-9 or r.std()<=1e-9: continue
            p=float(a.corr(r,method='pearson'));s=float(a.corr(r,method='spearman'))
            rows.append(dict(horizon=int(k),reliability=float(np.sqrt(max(0,p)*max(0,s)))))
        if rows:
            try: vals.append(fit_rho(pd.DataFrame(rows))[0])
            except ValueError: pass
    a=np.asarray(vals,float)
    return dict(n=int(len(a)),mean=float(a.mean()),median=float(np.median(a)),
                p025=float(np.quantile(a,.025)),p975=float(np.quantile(a,.975)),
                p10=float(np.quantile(a,.10)),p90=float(np.quantile(a,.90)))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--origins24',required=True);ap.add_argument('--origins25',required=True)
    ap.add_argument('--out',required=True);ap.add_argument('--seed',type=int,default=20261008);ap.add_argument('--bootstrap',type=int,default=1000)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    seasons=[];orders={};fits={};joins=[]
    for season,root,prefix in [('2024-25',a.origins24,'tc24-origin-'),('2025-26',a.origins25,'tc-origin-')]:
        p,order=panel(root,prefix,seed=a.seed);orders[season]=order
        m,j=matched_reliability(p);m['season']=season;j['season']=season
        rho,rmse=fit_rho(m);fits[season]=dict(rho_fh=rho,fit_rmse=rmse)
        seasons.append(m);joins.append(j)
    sm=pd.concat(seasons,ignore_index=True);joined=pd.concat(joins,ignore_index=True)
    pooled=(sm.groupby('horizon',as_index=False).agg(reliability=('reliability','mean'),pearson=('pearson','mean'),
             spearman=('spearman','mean'),mae=('mae','mean'),rmse=('rmse','mean'),n=('n','sum')))
    rho,rmse=fit_rho(pooled);pooled['fitted_reliability']=np.power(rho,pooled.horizon);pooled['fit_error']=pooled.reliability-pooled.fitted_reliability
    boot=bootstrap(joined,a.bootstrap,a.seed)
    sm.to_csv(out/'season_horizon_metrics.csv',index=False);pooled.to_csv(out/'pooled_fh_reliability_curve.csv',index=False)
    joined.to_csv(out/'matched_player_forecasts.csv.gz',index=False,compression='gzip')
    summary=dict(classification='FH squad-input reliability calibration from randomized historical forecast origins',
      method='Match each future top-player xP forecast to the same player near deadline; reliability=sqrt(Pearson*Spearman); equal-weight 2024/25 and 2025/26 by horizon; fit reliability=rho_FH^k.',
      realised_points_used=False,season_score_optimized=False,random_origin_order=orders,seed=a.seed,seasons=fits,
      pooled_rho_fh=rho,pooled_fit_rmse=rmse,bootstrap=boot,reliability_curve=pooled.to_dict('records'),
      interpretation='Calibrates decay of the player-value/ranking information feeding FH squad selection. It is not tuned to which historical FH week scored most points.')
    (out/'summary.json').write_text(json.dumps(summary,indent=2,default=str)+'\n');print(json.dumps(summary,indent=2,default=str))

if __name__=='__main__':main()
