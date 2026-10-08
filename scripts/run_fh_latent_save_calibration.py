#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from scipy.optimize import milp,LinearConstraint,Bounds
from scipy.sparse import lil_matrix

SEASONS=["2022-23","2023-24","2024-25","2025-26"]
POS={"GK":(2,1,1),"GKP":(2,1,1),"DEF":(5,3,5),"MID":(5,2,5),"FWD":(3,1,3)}

def load_gw(root:Path,season:str,gw:int):
    p=root/"data"/season/"gws"/f"gw{gw}.csv"
    if not p.exists(): return pd.DataFrame()
    z=pd.read_csv(p)
    z=z[z.position.astype(str).isin(POS)].copy()
    z["element"]=pd.to_numeric(z.element,errors="coerce")
    z["xP"]=pd.to_numeric(z.xP,errors="coerce").fillna(0.0)
    z["value"]=pd.to_numeric(z.value,errors="coerce")
    z=z.dropna(subset=["element","value"]).copy()
    z["element"]=z.element.astype(int)
    # Historical files can contain multiple fixture rows in DGW, but event xP is
    # repeated event-wide. Keep one player row to avoid double counting.
    z=(z.sort_values(["element","xP"],ascending=[True,False])
         .drop_duplicates("element",keep="first"))
    return z[["element","name","position","team","value","xP"]].copy()

def build_season(root,season):
    return {gw:load_gw(root,season,gw) for gw in range(1,39)}

def universe(gws,horizon):
    rows=[]
    for gw,w in horizon:
        z=gws.get(gw,pd.DataFrame())
        if z.empty: continue
        q=z.copy();q["gw"]=gw;q["w"]=w
        rows.append(q)
    if not rows:return pd.DataFrame()
    allr=pd.concat(rows,ignore_index=True)
    latest=(allr.sort_values("gw").drop_duplicates("element",keep="first")
            [["element","name","position","team","value"]])
    xp=(allr.assign(wx=allr.xP*allr.w).groupby("element",as_index=False).wx.sum())
    return latest.merge(xp,on="element",how="inner")

def optimise_squad(player_meta:pd.DataFrame,gw_tables:dict[int,pd.DataFrame],budget=1000):
    p=player_meta.reset_index(drop=True).copy();n=len(p)
    gws=sorted(gw_tables)
    # vars: x squad[n], then y_g[n], c_g[n] for each GW
    off_x=0;off={};N=n
    for gw in gws:
        off[gw]=(N,N+n);N+=2*n
    c=np.zeros(N,float)
    for gw,z in gw_tables.items():
        xp=p[["element"]].merge(z[["element","xP"]],on="element",how="left").xP.fillna(0).to_numpy(float)
        oy,oc=off[gw];c[oy:oy+n]=-xp;c[oc:oc+n]=-xp
    rows=[];lo=[];hi=[]
    def add(coefs,l,h):
        rows.append(coefs);lo.append(l);hi.append(h)
    # squad counts / budget / club
    for pos,(sq,_,_) in POS.items():
        idx=np.where(p.position.astype(str).eq(pos))[0]
        if pos=="GKP" and not len(idx):continue
        if pos=="GK":
            idx=np.where(p.position.astype(str).isin(["GK","GKP"]))[0]
        co={int(i):1 for i in idx};add(co,sq,sq)
    add({int(i):float(v) for i,v in enumerate(p.value)},-np.inf,float(budget))
    for team,idxs in p.groupby("team").indices.items():
        add({int(i):1 for i in idxs},-np.inf,3)
    for gw in gws:
        oy,oc=off[gw]
        add({oy+i:1 for i in range(n)},11,11)
        add({oc+i:1 for i in range(n)},1,1)
        for i in range(n):
            add({oy+i:1,i:-1},-np.inf,0)
            add({oc+i:1,oy+i:-1},-np.inf,0)
        idx=np.where(p.position.astype(str).isin(["GK","GKP"]))[0]
        add({oy+int(i):1 for i in idx},1,1)
        idx=np.where(p.position.astype(str).eq("DEF"))[0];add({oy+int(i):1 for i in idx},3,5)
        idx=np.where(p.position.astype(str).eq("MID"))[0];add({oy+int(i):1 for i in idx},2,5)
        idx=np.where(p.position.astype(str).eq("FWD"))[0];add({oy+int(i):1 for i in idx},1,3)
    A=lil_matrix((len(rows),N),dtype=float)
    for r,d in enumerate(rows):
        for j,v in d.items():A[r,j]=v
    res=milp(c,integrality=np.ones(N),bounds=Bounds(np.zeros(N),np.ones(N)),
             constraints=LinearConstraint(A.tocsr(),np.asarray(lo),np.asarray(hi)),
             options={"time_limit":20})
    if not res.success:raise RuntimeError(str(res.message))
    x=res.x[:n]>0.5
    squad=p.loc[x,"element"].astype(int).tolist()
    scores={}
    for gw,z in gw_tables.items():
        oy,oc=off[gw]
        xp=p[["element"]].merge(z[["element","xP"]],on="element",how="left").xP.fillna(0).to_numpy(float)
        scores[gw]=float(np.dot(res.x[oy:oy+n],xp)+np.dot(res.x[oc:oc+n],xp))
    return squad,scores

def opportunity_curve(root:Path,season:str):
    gws=build_season(root,season);rows=[]
    for gw in range(1,39):
        cur=gws[gw]
        if cur.empty:continue
        end=min(38,gw+5)
        horizon=[(k,1.0) for k in range(gw,end+1)]
        meta=universe(gws,horizon)
        # Require players to be present in current price/position ledger.
        curmeta=cur[["element","name","position","team","value"]].copy()
        future_xp={}
        for k in range(gw,end+1):
            future_xp[k]=gws[k][["element","xP"]].copy()
        # One-week optimal FH squad.
        _,fhscore=optimise_squad(curmeta,{gw:future_xp[gw]})
        # Medium-term permanent squad, same legal budget and current prices.
        _,longscores=optimise_squad(curmeta,future_xp)
        gain=max(0.0,float(fhscore[gw]-longscores[gw]))
        rows.append(dict(season=season,gw=gw,fh_proxy_gain=gain,
                         one_week_score=float(fhscore[gw]),six_week_squad_score=float(longscores[gw]),
                         horizon_end=end))
        print(f"{season} GW{gw}: latent FH proxy {gain:.3f}",flush=True)
    return pd.DataFrame(rows)

def latent_prior(allgw):
    rows=[]
    for start,end,half in [(1,19,"H1"),(20,38,"H2")]:
        for gw in range(start,end+1):
            vals=[];bestgws=[]
            for s in SEASONS:
                z=allgw[(allgw.season.eq(s))&allgw.gw.between(gw+1,end)]
                if z.empty:
                    vals.append(0.0);continue
                i=z.fh_proxy_gain.idxmax();vals.append(float(z.loc[i,"fh_proxy_gain"]));bestgws.append(int(z.loc[i,"gw"]))
            rows.append(dict(half=half,gw=gw,seasons=len(vals),
                latent_fh_save_mean=float(np.mean(vals)),
                latent_fh_save_median=float(np.median(vals)),
                latent_fh_save_p75=float(np.quantile(vals,.75)),
                p_future_gain_ge5=float(np.mean(np.asarray(vals)>=5)),
                p_future_gain_ge10=float(np.mean(np.asarray(vals)>=10)),
                mean_best_future_gw=(float(np.mean(bestgws)) if bestgws else np.nan)))
    return pd.DataFrame(rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--vaastav",required=True);ap.add_argument("--out",required=True)
    a=ap.parse_args();root=Path(a.vaastav);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    curves=[opportunity_curve(root,s) for s in SEASONS]
    allgw=pd.concat(curves,ignore_index=True);prior=latent_prior(allgw)
    allgw.to_csv(out/"historical_fh_proxy_by_gw.csv",index=False)
    prior.to_csv(out/"latent_fh_save_by_gw.csv",index=False)
    summary={"classification":"Four-season latent FH save-value calibration from pre-GW xP only",
      "seasons":SEASONS,
      "method":"For each historical GW, compare legal one-week optimal 15-man squad score with a legal squad optimized over GW..GW+5 using current prices; FH proxy is positive current-GW score gap. Latent save at GW g is the across-season distribution of the best later proxy remaining in that chip half.",
      "realised_points_used":False,"season_score_optimized":False,
      "prior_by_gw":prior.to_dict("records")}
    (out/"summary.json").write_text(json.dumps(summary,indent=2,default=str)+"\n")
    print(json.dumps(summary,indent=2,default=str))

if __name__=="__main__":main()
