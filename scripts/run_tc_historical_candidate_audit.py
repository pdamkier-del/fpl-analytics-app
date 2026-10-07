#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd

SEASONS=["2022-23","2023-24","2024-25","2025-26"]
VARIANTS={
 "mean":dict(mode="mean",tol=0.0),
 "q75_tb_050":dict(mode="q75",tol=.50),
 "q75_tb_075":dict(mode="q75",tol=.75),
 "q75_tb_100":dict(mode="q75",tol=1.00),
 "p10_tb_100":dict(mode="p10",tol=1.00),
 "p15_tb_100":dict(mode="p15",tol=1.00),
}

def load_season(root:Path,season:str):
    rows=[]
    for gw in range(1,39):
        p=root/"data"/season/"gws"/f"gw{gw}.csv"
        if not p.exists(): continue
        z=pd.read_csv(p)
        z["GW"]=gw
        rows.append(z)
    x=pd.concat(rows,ignore_index=True)
    x["xP"]=pd.to_numeric(x["xP"],errors="coerce")
    x["total_points"]=pd.to_numeric(x["total_points"],errors="coerce").fillna(0.)
    x["minutes"]=pd.to_numeric(x["minutes"],errors="coerce").fillna(0.)
    x=x[x["position"].astype(str).isin(["GK","GKP","DEF","MID","FWD"])].copy()
    return x

def add_past_upside(x):
    x=x.sort_values(["element","GW"]).copy()
    q75=[];p10=[];p15=[];nprev=[]
    history={}
    for r in x.itertuples(index=False):
        h=history.get(int(r.element),[])
        vals=np.asarray(h,float)
        q75.append(float(np.quantile(vals,.75)) if len(vals)>=3 else np.nan)
        p10.append(float((vals>=10).mean()) if len(vals)>=3 else np.nan)
        p15.append(float((vals>=15).mean()) if len(vals)>=3 else np.nan)
        nprev.append(len(vals))
        if float(r.minutes)>0:
            history.setdefault(int(r.element),[]).append(float(r.total_points))
    x["past_q75"]=q75;x["past_p10"]=p10;x["past_p15"]=p15;x["nprev"]=nprev
    return x

def choose(g,var):
    g=g[g.xP.notna()].copy()
    if g.empty:return None
    maxxp=float(g.xP.max())
    eligible=g[g.xP>=maxxp-float(var["tol"])].copy()
    mode=var["mode"]
    if mode=="mean":
        return eligible.sort_values(["xP","selected"],ascending=False).iloc[0]
    metric={"q75":"past_q75","p10":"past_p10","p15":"past_p15"}[mode]
    known=eligible[eligible[metric].notna()].copy()
    if known.empty:
        return eligible.sort_values(["xP","selected"],ascending=False).iloc[0]
    return known.sort_values([metric,"xP"],ascending=False).iloc[0]

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--vaastav",required=True);ap.add_argument("--out",required=True)
    a=ap.parse_args();root=Path(a.vaastav);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    picks=[]
    for season in SEASONS:
        x=add_past_upside(load_season(root,season))
        for gw,g in x.groupby("GW",sort=True):
            maxxp=float(g.xP.max()) if g.xP.notna().any() else np.nan
            # TC-worthy subset diagnostic: still record every GW, flag high-xP spots.
            for vname,var in VARIANTS.items():
                r=choose(g,var)
                if r is None:continue
                picks.append(dict(
                  season=season,gw=int(gw),variant=vname,element=int(r.element),name=str(r["name"]),
                  position=str(r.position),team=str(r.team),xP=float(r.xP),max_xP=maxxp,
                  xp_sacrifice=maxxp-float(r.xP),past_q75=(None if pd.isna(r.past_q75) else float(r.past_q75)),
                  past_p10=(None if pd.isna(r.past_p10) else float(r.past_p10)),
                  past_p15=(None if pd.isna(r.past_p15) else float(r.past_p15)),
                  actual_points=float(r.total_points),home=bool(r.was_home),
                  opponent_team=int(r.opponent_team),tc_worthy=bool(maxxp>=6.0)
                ))
    p=pd.DataFrame(picks)
    summaries=[]
    for scope,mask in [("all_gws",pd.Series(True,index=p.index)),("tc_worthy_maxxp_ge6",p.tc_worthy)]:
      z=p[mask]
      for v,g in z.groupby("variant"):
        summaries.append(dict(scope=scope,variant=v,n=len(g),actual_mean=float(g.actual_points.mean()),
          actual_total=float(g.actual_points.sum()),hit10=float((g.actual_points>=10).mean()),
          hit15=float((g.actual_points>=15).mean()),avg_xp_sacrifice=float(g.xp_sacrifice.mean()),
          changed_from_top_xp=int((g.xp_sacrifice>1e-9).sum())))
    s=pd.DataFrame(summaries)
    p.to_csv(out/"historical_candidate_picks.csv",index=False);s.to_csv(out/"historical_candidate_summary.csv",index=False)
    (out/"summary.json").write_text(json.dumps({"classification":"cutoff-safe per-GW candidate upside diagnostic using archived pre-GW xP and prior actual points only","seasons":SEASONS,"variants":VARIANTS,"summary":s.to_dict("records")},indent=2,default=str)+"\n")
    print(s.to_string(index=False))

if __name__=="__main__":main()
