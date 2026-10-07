#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
import run_horizon_policy_comparison as hp

VARIANTS={
  "mean": dict(tol=0.0,metric="mean"),
  "q75_tiebreak_0p50": dict(tol=.50,metric="q75"),
  "q75_tiebreak_0p75": dict(tol=.75,metric="q75"),
  "q75_tiebreak_1p00": dict(tol=1.00,metric="q75"),
  "p15_tiebreak_1p00": dict(tol=1.00,metric="p15"),
}

def load_origin(root,gw):
    p=root/f"tc-origin-{gw}"/"tc_samples.csv.gz"
    if not p.exists(): raise FileNotFoundError(p)
    return pd.read_csv(p)

def stats(samples):
    grp=samples.groupby(["gw","candidate_id","candidate_name"],sort=False).points
    s=grp.agg(mean="mean").reset_index()
    q=grp.quantile(.75).rename("q75").reset_index()
    p=grp.apply(lambda x:float((x>=15).mean())).rename("p15").reset_index()
    return s.merge(q,on=["gw","candidate_id","candidate_name"]).merge(p,on=["gw","candidate_id","candidate_name"])

def choose_per_gw(samples,var):
    s=stats(samples)
    rows=[]
    for gw,g in s.groupby("gw",sort=True):
        maxmean=float(g["mean"].max())
        eligible=g[g["mean"]>=maxmean-float(var["tol"])].copy()
        if var["metric"]=="mean":
            pick=eligible.sort_values(["mean","q75"],ascending=False).iloc[0]
        elif var["metric"]=="q75":
            pick=eligible.sort_values(["q75","mean"],ascending=False).iloc[0]
        elif var["metric"]=="p15":
            pick=eligible.sort_values(["p15","mean"],ascending=False).iloc[0]
        rows.append(pick)
    return pd.DataFrame(rows)

def timing(samples,var,current,end,discount):
    chosen=choose_per_gw(samples,var).sort_values("gw")
    chosen["decision_value"]=chosen["mean"]
    chosen["adjusted_value"]=chosen["decision_value"]*np.power(discount,chosen.gw-current)
    fixed=samples.merge(chosen[["gw","candidate_id"]],on=["gw","candidate_id"],how="inner")
    fixed["adjusted_points"]=fixed.points*np.power(discount,fixed.gw-current)
    win=(fixed.sort_values(["simulation","adjusted_points","gw"],ascending=[True,False,True])
         .groupby("simulation",sort=False).head(1))
    n=win.simulation.nunique();counts=win.gw.value_counts().to_dict()
    chosen["probability_best"]=[float(counts.get(int(g),0)/n) for g in chosen.gw]
    return chosen

def replay_half(root,start,end,var,discount):
    trace=[];decision=None
    for gw in range(start,end+1):
        samples=load_origin(root,gw)
        ch=timing(samples,var,gw,end,discount)
        cur=ch[ch.gw.eq(gw)].iloc[0]
        fut=ch[ch.gw.gt(gw)]
        save=0.0 if fut.empty else float(fut.adjusted_value.max())
        edge=float(cur.decision_value-save)
        use=(gw==end) or edge>=0
        trace.append(dict(
          gw=gw,candidate_id=int(cur.candidate_id),candidate_name=str(cur.candidate_name),
          mean=float(cur["mean"]),q75=float(cur.q75),p15=float(cur.p15),
          probability_best=float(cur.probability_best),save_option=save,edge=edge,
          action="USE_TC" if use else "SAVE_TC"
        ))
        if use: decision=trace[-1].copy();break
    return decision,pd.DataFrame(trace)

def actual_table():
    gws=hp.unpack_runtime("merged_gw.csv")
    raw=hp.unpack_runtime("players_raw.csv").drop_duplicates("id")
    names=raw.set_index("id").web_name.astype(str).to_dict()
    a=gws.groupby(["GW","element"],as_index=False).agg(actual_points=("total_points","sum"))
    a["name"]=a.element.map(names).fillna(a.element.astype(str))
    return a

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--origins",required=True);ap.add_argument("--out",required=True);ap.add_argument("--discount",type=float,default=.97)
    a=ap.parse_args();root=Path(a.origins);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    actual=actual_table();ds=[];ts=[]
    for name,var in VARIANTS.items():
      for start,end in [(6,19),(20,38)]:
        d,t=replay_half(root,start,end,var,a.discount);d.update(variant=name,half=f"{start}-{end}");t["variant"]=name;t["half"]=f"{start}-{end}";ds.append(d);ts.append(t)
    d=pd.DataFrame(ds)
    d=d.merge(actual[["GW","element","actual_points"]],left_on=["gw","candidate_id"],right_on=["GW","element"],how="left").drop(columns=["GW","element"])
    totals=d.groupby("variant",as_index=False).agg(actual_tc_added=("actual_points","sum"),mean_forecast=("mean","mean")).sort_values("actual_tc_added",ascending=False)
    d.to_csv(out/"decisions.csv",index=False);pd.concat(ts).to_csv(out/"traces.csv",index=False);totals.to_csv(out/"totals.csv",index=False)
    (out/"summary.json").write_text(json.dumps({"classification":"TC upside tie-break sensitivity; diagnostic only","variants":VARIANTS,"decisions":d.to_dict("records"),"totals":totals.to_dict("records")},indent=2,default=str)+"\n")
    print(totals.to_string(index=False));print(d.to_string(index=False))
if __name__=="__main__":main()
