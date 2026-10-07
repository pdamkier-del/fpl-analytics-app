#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd

def load_origin(root:Path,prefix:str,gw:int)->pd.DataFrame:
    p=root/f"{prefix}{gw}"/"tc_candidates.csv"
    if not p.exists(): raise FileNotFoundError(p)
    z=pd.read_csv(p)
    return z[["gw","candidate_id","candidate_name","mean_points"]].copy()

def build_panel(root:Path,prefix:str,start:int=6,end:int=38):
    rows=[]
    for origin in range(start,end+1):
        z=load_origin(root,prefix,origin)
        z["origin"]=origin
        z["horizon"]=z.gw-origin
        rows.append(z)
    return pd.concat(rows,ignore_index=True)

def final_reference(panel:pd.DataFrame):
    # Same-GW forecast from the latest available origin is our "near-deadline" reference.
    ref=(panel[panel.horizon.eq(0)]
         .rename(columns={"mean_points":"ref_mean","origin":"ref_origin"})
         [["gw","candidate_id","ref_mean","ref_origin"]])
    return ref

def horizon_metrics(panel:pd.DataFrame):
    ref=final_reference(panel)
    x=panel.merge(ref,on=["gw","candidate_id"],how="inner")
    x=x[x.horizon>=0].copy()
    rows=[]
    for k,g in x.groupby("horizon",sort=True):
        if len(g)<20: continue
        a=g.mean_points.to_numpy(float);b=g.ref_mean.to_numpy(float)
        mae=float(np.mean(np.abs(a-b)))
        rmse=float(np.sqrt(np.mean((a-b)**2)))
        corr=float(np.corrcoef(a,b)[0,1]) if np.std(a)>1e-9 and np.std(b)>1e-9 else np.nan
        # signal retention: regression slope through origin-ish covariance/variance
        slope=float(np.cov(a,b,ddof=0)[0,1]/np.var(b)) if np.var(b)>1e-12 else np.nan
        rows.append(dict(horizon=int(k),n=len(g),mae=mae,rmse=rmse,corr=corr,slope=slope))
    return pd.DataFrame(rows),x

def rank_metrics(panel:pd.DataFrame):
    # How well does an origin forecast rank the eventual near-deadline candidate set?
    ref=final_reference(panel)
    x=panel.merge(ref,on=["gw","candidate_id"],how="inner")
    out=[]
    for (origin,gw),g in x.groupby(["origin","gw"]):
        k=int(gw-origin)
        if k<0 or len(g)<3: continue
        r1=g.mean_points.rank(method="average")
        r2=g.ref_mean.rank(method="average")
        spearman=float(r1.corr(r2))
        top_now=int(g.loc[g.mean_points.idxmax(),"candidate_id"])
        top_ref=int(g.loc[g.ref_mean.idxmax(),"candidate_id"])
        out.append(dict(origin=int(origin),gw=int(gw),horizon=k,spearman=spearman,top1_match=float(top_now==top_ref)))
    z=pd.DataFrame(out)
    return z.groupby("horizon",as_index=False).agg(
        rank_spearman=("spearman","mean"),top1_match=("top1_match","mean"),n_gws=("gw","count")
    )

def fit_d(metrics:pd.DataFrame):
    # Reliability target combines correlation and rank preservation.
    m=metrics.copy()
    m=m[m.horizon>0].dropna(subset=["reliability"])
    if m.empty: raise ValueError("no nonzero horizons")
    ks=m.horizon.to_numpy(float);r=np.clip(m.reliability.to_numpy(float),1e-6,1)
    # Fit log r = k log d through origin.
    logd=float(np.sum(ks*np.log(r))/np.sum(ks*ks))
    d=float(np.exp(logd))
    pred=np.power(d,ks)
    rmse=float(np.sqrt(np.mean((pred-r)**2)))
    return d,rmse

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--origins24",required=True);ap.add_argument("--origins25",required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)

    all_metrics=[];all_rank=[];fits={}
    for season,root,prefix in [
        ("2024-25",Path(a.origins24),"tc24-origin-"),
        ("2025-26",Path(a.origins25),"tc-origin-"),
    ]:
        panel=build_panel(root,prefix)
        hm,_=horizon_metrics(panel)
        rm=rank_metrics(panel)
        m=hm.merge(rm,on="horizon",how="left")
        # Correlation drives numeric forecast retention; rank-signal prevents
        # treating a perfectly shifted/scaled forecast as fully reliable.
        m["reliability"]=np.sqrt(
            np.clip(m["corr"],0,1)*np.clip(m["rank_spearman"].fillna(m["corr"]),0,1)
        )
        m["season"]=season
        d,fitrmse=fit_d(m)
        fits[season]={"d":d,"fit_rmse":fitrmse}
        all_metrics.append(m);all_rank.append(rm.assign(season=season))

    metrics=pd.concat(all_metrics,ignore_index=True)
    # Equal-season weighting by averaging reliability at each horizon first.
    pooled=(metrics.groupby("horizon",as_index=False)
            .agg(reliability=("reliability","mean"),corr=("corr","mean"),
                 rank_spearman=("rank_spearman","mean"),top1_match=("top1_match","mean")))
    d,fitrmse=fit_d(pooled)
    pooled["fitted_reliability"]=np.power(d,pooled.horizon)
    pooled["fit_error"]=pooled.reliability-pooled.fitted_reliability

    # Also report a direct empirical curve normalized to horizon 0=1.
    summary={
      "classification":"Empirical TC future-forecast reliability calibration",
      "method":"Compare long-horizon TC candidate xP with same-GW near-deadline forecast; reliability=sqrt(Pearson xP correlation * Spearman ranking correlation), equal-weight seasons; fit reliability ~= d^k.",
      "seasons":fits,
      "pooled_d":d,
      "pooled_fit_rmse":fitrmse,
      "horizons":pooled.to_dict("records"),
      "note":"This calibrates forecast information decay, not realised TC points."
    }
    metrics.to_csv(out/"season_horizon_metrics.csv",index=False)
    pooled.to_csv(out/"pooled_reliability_curve.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2,default=str)+"\n")
    print(json.dumps(summary,indent=2,default=str))

if __name__=="__main__":main()
