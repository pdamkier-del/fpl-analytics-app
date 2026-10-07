#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd

POLICIES={
 "d_0p97": {"kind":"exp","d":0.97},
 "d_0p969_fit": {"kind":"exp","d":0.968713091424214},
 "d_0p94": {"kind":"exp","d":0.94},
 "two_stage_fit": {"kind":"two","a":0.7204790397883253,"d":0.9938198453588738},
 "empirical_curve": {"kind":"curve","values":[1.0,0.7572751521131194,0.7032843858581395,0.7047189482895067,0.7294450774664305,0.6880248132392998,0.6620089774056516,0.6816599534494022,0.7101325898781952,0.6529360545248581,0.7087400991235955,0.6672920340616874,0.6971400904834832,0.5674284775030258,0.5791542145584311,0.745201742667648,0.6785355419273525,0.8894051176011658]}
}

def w(policy,k):
    if k==0:return 1.0
    if policy["kind"]=="exp":return float(policy["d"]**k)
    if policy["kind"]=="two":return float(policy["a"]*(policy["d"]**(k-1)))
    vals=policy["values"]
    return float(vals[k] if k<len(vals) else vals[-1])

def load(root,prefix,gw):
    p=Path(root)/f"{prefix}{gw}"/"tc_samples.csv.gz"
    if not p.exists():raise FileNotFoundError(p)
    return pd.read_csv(p)

def choose_mean(samples):
    s=(samples.groupby(["gw","candidate_id","candidate_name"],as_index=False).points.mean()
       .rename(columns={"points":"mean"}))
    idx=s.groupby("gw").mean.idxmax()
    return s.loc[idx].sort_values("gw").reset_index(drop=True)

def replay_half(root,prefix,start,end,policy):
    trace=[];decision=None
    for gw in range(start,end+1):
        s=load(root,prefix,gw)
        ch=choose_mean(s)
        ch["weight"]=[w(policy,int(g-gw)) for g in ch.gw]
        ch["adj"]=ch["mean"]*ch["weight"]
        cur=ch[ch.gw.eq(gw)].iloc[0]
        fut=ch[ch.gw.gt(gw)]
        save=0.0 if fut.empty else float(fut.adj.max())
        edge=float(cur["mean"]-save)
        use=(gw==end) or edge>=0
        trace.append(dict(gw=gw,candidate_id=int(cur.candidate_id),candidate_name=str(cur.candidate_name),
                          mean=float(cur["mean"]),save_option=save,edge=edge,action="USE_TC" if use else "SAVE_TC"))
        if use:
            decision=trace[-1].copy();break
    return decision,pd.DataFrame(trace)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--origins24",required=True);ap.add_argument("--origins25",required=True);ap.add_argument("--out",required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    rows=[];traces=[]
    for pname,p in POLICIES.items():
      for season,root,prefix in [("2024-25",a.origins24,"tc24-origin-"),("2025-26",a.origins25,"tc-origin-")]:
        for start,end in [(6,19),(20,38)]:
          d,t=replay_half(root,prefix,start,end,p);d.update(policy=pname,season=season,half=f"{start}-{end}")
          t["policy"]=pname;t["season"]=season;t["half"]=f"{start}-{end}"
          rows.append(d);traces.append(t)
    dec=pd.DataFrame(rows);tr=pd.concat(traces,ignore_index=True)
    dec.to_csv(out/"discount_policy_decisions.csv",index=False);tr.to_csv(out/"discount_policy_traces.csv",index=False)
    (out/"summary.json").write_text(json.dumps({"classification":"TC discount policy timing comparison","policies":POLICIES,"decisions":dec.to_dict("records")},indent=2,default=str)+"\n")
    print(dec.to_string(index=False))

if __name__=="__main__":main()
