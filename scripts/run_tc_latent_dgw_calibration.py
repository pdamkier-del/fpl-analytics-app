#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd

SEASONS=["2022-23","2023-24","2024-25","2025-26"]
VALID={"GK","GKP","DEF","MID","FWD"}

def season_gws(root:Path,season:str)->pd.DataFrame:
    rows=[]
    for gw in range(1,39):
        p=root/"data"/season/"gws"/f"gw{gw}.csv"
        if not p.exists(): continue
        z=pd.read_csv(p)
        z=z[z.position.astype(str).isin(VALID)].copy()
        z["GW"]=gw
        z["xP"]=pd.to_numeric(z["xP"],errors="coerce")
        z["element"]=pd.to_numeric(z["element"],errors="coerce")
        rows.append(z)
    x=pd.concat(rows,ignore_index=True)
    return x

def summarize_season(x:pd.DataFrame,season:str):
    out=[]
    for gw,g in x.groupby("GW",sort=True):
        counts=g.groupby("element").size()
        dgw=bool((counts>1).any())
        # event xP is repeated on each fixture row in historical files; de-dupe players.
        players=g.sort_values("xP",ascending=False).drop_duplicates("element")
        top=players[players.xP.notna()].head(1)
        if top.empty: continue
        r=top.iloc[0]
        out.append(dict(season=season,gw=int(gw),is_dgw=dgw,
                        top_xp=float(r.xP),top_name=str(r["name"]),
                        top_element=int(r.element)))
    return pd.DataFrame(out)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--vaastav",required=True);ap.add_argument("--out",required=True)
    a=ap.parse_args();root=Path(a.vaastav);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    allgw=pd.concat([summarize_season(season_gws(root,s),s) for s in SEASONS],ignore_index=True)

    sgw=allgw[~allgw.is_dgw].top_xp
    dgw=allgw[allgw.is_dgw].top_xp
    mu_sgw=float(sgw.mean());mu_dgw=float(dgw.mean())
    uplift=float(np.mean(np.maximum(dgw.to_numpy(float)-mu_sgw,0.0)))
    med_uplift=float(np.median(np.maximum(dgw.to_numpy(float)-mu_sgw,0.0)))

    priors=[]
    for start,end,label in [(1,19,"H1"),(20,38,"H2")]:
        for gw in range(start,end+1):
            vals=[]
            for s in SEASONS:
                z=allgw[(allgw.season==s)&allgw.gw.between(gw+1,end)]
                vals.append(float(z.is_dgw.any()))
            priors.append(dict(half=label,gw=gw,seasons=len(vals),
                               p_any_future_dgw=float(np.mean(vals)),
                               n_seasons_future_dgw=int(sum(vals))))
    prior=pd.DataFrame(priors)

    # Also count distribution of number of DGW gameweeks in each half.
    counts=(allgw.groupby(["season"])
            .apply(lambda g:pd.Series({
              "dgw_h1":int(g[g.gw.between(1,19)].is_dgw.sum()),
              "dgw_h2":int(g[g.gw.between(20,38)].is_dgw.sum()),
              "dgw_total":int(g.is_dgw.sum())
            }),include_groups=False).reset_index())

    allgw.to_csv(out/"gw_dgw_audit.csv",index=False)
    prior.to_csv(out/"latent_dgw_prior_by_gw.csv",index=False)
    counts.to_csv(out/"season_dgw_counts.csv",index=False)
    summary={
      "classification":"Four-season structural DGW prior and pre-GW xP uplift audit",
      "seasons":SEASONS,
      "sgw_count":int(len(sgw)),"dgw_count":int(len(dgw)),
      "mean_top_xp_sgw":mu_sgw,"mean_top_xp_dgw":mu_dgw,
      "mean_positive_dgw_uplift_over_sgw_mean":uplift,
      "median_positive_dgw_uplift_over_sgw_mean":med_uplift,
      "season_counts":counts.to_dict("records"),
      "prior_by_gw":prior.to_dict("records"),
      "formula":"latent_value = mu_TC + p_unresolved_future_dgw * expected_positive_dgw_uplift"
    }
    (out/"summary.json").write_text(json.dumps(summary,indent=2,default=str)+"\n")
    print(json.dumps(summary,indent=2,default=str))
if __name__=="__main__":main()
