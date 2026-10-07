#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd

# Empirical pooled reliability curve from tc-discount-calibration.
R=[1.0,0.7572751521131194,0.7032843858581395,0.7047189482895067,0.7294450774664305,
   0.6880248132392998,0.6620089774056516,0.6816599534494022,0.7101325898781952,
   0.6529360545248581,0.7087400991235955,0.6672920340616874,0.6971400904834832,
   0.5674284775030258,0.5791542145584311,0.745201742667648,0.6785355419273525,
   0.8894051176011658]

def rweight(k:int)->float:
    if k<=0:return 1.0
    return float(R[k] if k<len(R) else np.nanmedian(R[5:13]))

def load_origin(root:Path,prefix:str,gw:int)->pd.DataFrame:
    p=root/f"{prefix}{gw}"/"tc_samples.csv.gz"
    if not p.exists():raise FileNotFoundError(p)
    return pd.read_csv(p)

def choose_tc(samples:pd.DataFrame)->pd.DataFrame:
    grp=samples.groupby(["gw","candidate_id","candidate_name"],sort=False).points
    s=grp.agg(mean="mean").reset_index()
    s=s.merge(grp.quantile(.75).rename("q75").reset_index(),
              on=["gw","candidate_id","candidate_name"],how="left")
    rows=[]
    for gw,g in s.groupby("gw",sort=True):
        maxmean=float(g["mean"].max())
        eligible=g[g["mean"]>=maxmean-0.50].copy()
        rows.append(eligible.sort_values(["q75","mean"],ascending=False).iloc[0])
    return pd.DataFrame(rows).sort_values("gw").reset_index(drop=True)

def estimate_mu_from_origins(root:Path,prefix:str,start=6,end=38)->float:
    vals=[]
    for gw in range(start,end+1):
        s=load_origin(root,prefix,gw)
        ch=choose_tc(s)
        cur=ch[ch.gw.eq(gw)]
        if len(cur):vals.append(float(cur.iloc[0]["mean"]))
    if not vals:raise ValueError("no current-GW best-xP values for mu")
    return float(np.mean(vals))

def replay_half(root,prefix,start,end,mu,policy):
    trace=[];decision=None
    for gw in range(start,end+1):
        s=load_origin(root,prefix,gw)
        ch=choose_tc(s)
        if policy=="regress":
            ch["adj"]=[float(mu + rweight(int(g-gw))*(m-mu)) for g,m in zip(ch.gw,ch["mean"])]
        elif policy=="d097":
            ch["adj"]=[float(m*(0.97**int(g-gw))) for g,m in zip(ch.gw,ch["mean"])]
        else:
            raise ValueError(policy)
        cur=ch[ch.gw.eq(gw)].iloc[0]
        fut=ch[ch.gw.gt(gw)]
        save=0.0 if fut.empty else float(fut.adj.max())
        edge=float(cur["mean"]-save)
        use=(gw==end) or edge>=0
        trace.append(dict(
          gw=gw,candidate_id=int(cur.candidate_id),candidate_name=str(cur.candidate_name),
          mean=float(cur["mean"]),save_option=save,edge=edge,
          action="USE_TC" if use else "SAVE_TC"
        ))
        if use:
            decision=trace[-1].copy();break
    if decision is None:raise RuntimeError("No decision")
    return decision,pd.DataFrame(trace)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--origins24",required=True);ap.add_argument("--origins25",required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args();o=Path(a.out);o.mkdir(parents=True,exist_ok=True)
    roots=[("2024-25",Path(a.origins24),"tc24-origin-"),("2025-26",Path(a.origins25),"tc-origin-")]
    mus={s:estimate_mu_from_origins(r,p) for s,r,p in roots}
    pooled=float(np.mean(list(mus.values())))
    rows=[];tr=[]
    for policy in ["d097","regress"]:
      for season,root,prefix in roots:
        for start,end in [(6,19),(20,38)]:
          d,t=replay_half(root,prefix,start,end,pooled,policy)
          d.update(policy=policy,season=season,half=f"{start}-{end}",mu_tc=pooled)
          t["policy"]=policy;t["season"]=season;t["half"]=f"{start}-{end}";t["mu_tc"]=pooled
          rows.append(d);tr.append(t)
    dec=pd.DataFrame(rows);trace=pd.concat(tr,ignore_index=True)
    dec.to_csv(o/"regression_policy_decisions.csv",index=False)
    trace.to_csv(o/"regression_policy_traces.csv",index=False)
    summary={
      "classification":"TC future-value regression-to-baseline test",
      "mu_by_season":mus,
      "mu_pooled":pooled,
      "reliability_curve":R,
      "formula":"V_adj = mu_TC + R_k * (xP - mu_TC)",
      "candidate_rule":"highest q75 among players within 0.50 xP of the max mean",
      "decisions":dec.to_dict("records")
    }
    (o/"summary.json").write_text(json.dumps(summary,indent=2,default=str)+"\n")
    print(json.dumps(summary,indent=2,default=str))
if __name__=="__main__":main()
