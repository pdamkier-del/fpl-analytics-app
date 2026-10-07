#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import run_horizon_policy_comparison as hp

VARIANTS={
 "mean":dict(mode="mean"),
 "q75_bonus_025":dict(mode="qbonus",lam=.25),
 "q75_bonus_050":dict(mode="qbonus",lam=.50),
 "p10_bonus_2":dict(mode="tailbonus",thr=10.,lam=2.),
 "p15_bonus_4":dict(mode="tailbonus",thr=15.,lam=4.),
 "q75_tiebreak_050":dict(mode="tiebreak",metric="q75",tol=.50),
 "q75_tiebreak_075":dict(mode="tiebreak",metric="q75",tol=.75),
 "q75_tiebreak_100":dict(mode="tiebreak",metric="q75",tol=1.00),
 "p15_tiebreak_100":dict(mode="tiebreak",metric="p15",tol=1.00),
}

def load_origin(root:Path,prefix:str,gw:int)->pd.DataFrame:
    p=root/f"{prefix}{gw}"/"tc_samples.csv.gz"
    if not p.exists(): raise FileNotFoundError(p)
    return pd.read_csv(p)

def stats(samples):
    grp=samples.groupby(["gw","candidate_id","candidate_name"],sort=False).points
    s=grp.agg(mean="mean").reset_index()
    s=s.merge(grp.quantile(.75).rename("q75").reset_index(),on=["gw","candidate_id","candidate_name"])
    for thr,name in [(10.,"p10"),(15.,"p15")]:
        p=grp.apply(lambda x,t=thr:float((x>=t).mean())).rename(name).reset_index()
        s=s.merge(p,on=["gw","candidate_id","candidate_name"])
    return s

def score_stats(s,var):
    x=s.copy()
    mode=var["mode"]
    if mode=="mean":
        x["score"]=x["mean"]
    elif mode=="qbonus":
        x["score"]=x["mean"]+float(var["lam"])*(x["q75"]-x["mean"])
    elif mode=="tailbonus":
        col="p10" if float(var["thr"])==10 else "p15"
        x["score"]=x["mean"]+float(var["lam"])*x[col]
    elif mode=="tiebreak":
        x["score"]=x["mean"]
    else: raise ValueError(var)
    return x

def choose_per_gw(samples,var):
    s=score_stats(stats(samples),var);rows=[]
    for gw,g in s.groupby("gw",sort=True):
        if var["mode"]=="tiebreak":
            maxmean=float(g["mean"].max());e=g[g["mean"]>=maxmean-float(var["tol"])].copy()
            metric=str(var["metric"]);pick=e.sort_values([metric,"mean"],ascending=False).iloc[0]
        else:
            pick=g.sort_values(["score","mean"],ascending=False).iloc[0]
        rows.append(pick)
    return pd.DataFrame(rows)

def replay_half(root,prefix,start,end,var,discount):
    trace=[];decision=None
    for gw in range(start,end+1):
        samples=load_origin(root,prefix,gw)
        ch=choose_per_gw(samples,var).sort_values("gw")
        # Timing value uses the variant score for bonus variants, but mean xP for
        # tie-break variants: a tie-break changes candidate choice, not TC timing utility.
        if var["mode"]=="tiebreak":
            ch["decision_value"]=ch["mean"]
        else:
            ch["decision_value"]=ch["score"]
        ch["adjusted_value"]=ch["decision_value"]*np.power(discount,ch.gw-gw)
        cur=ch[ch.gw.eq(gw)].iloc[0];future=ch[ch.gw.gt(gw)]
        save=0.0 if future.empty else float(future.adjusted_value.max())
        edge=float(cur.decision_value-save);use=(gw==end) or edge>=0

        # Diagnostic timing probability with the selected player fixed ex ante.
        fixed=samples.merge(ch[["gw","candidate_id"]],on=["gw","candidate_id"],how="inner")
        fixed["adjusted_points"]=fixed.points*np.power(discount,fixed.gw-gw)
        win=(fixed.sort_values(["simulation","adjusted_points","gw"],ascending=[True,False,True])
             .groupby("simulation",sort=False).head(1))
        pbest=float((win.gw==gw).mean())

        gstats=stats(samples);gcur=gstats[gstats.gw.eq(gw)]
        maxmean=float(gcur["mean"].max())
        trace.append(dict(gw=gw,candidate_id=int(cur.candidate_id),candidate_name=str(cur.candidate_name),
          mean=float(cur["mean"]),q75=float(cur.q75),p10=float(cur.p10),p15=float(cur.p15),
          score=float(cur.score),best_mean_same_gw=maxmean,mean_sacrifice=maxmean-float(cur["mean"]),
          p_current_best=pbest,save_option=save,edge=edge,action="USE_TC" if use else "SAVE_TC"))
        if use:
            decision=trace[-1].copy();break
    if decision is None:raise RuntimeError("No TC decision")
    return decision,pd.DataFrame(trace)

def actual25():
    gws=hp.unpack_runtime("merged_gw.csv");raw=hp.unpack_runtime("players_raw.csv").drop_duplicates("id")
    names=raw.set_index("id").web_name.astype(str).to_dict()
    a=gws.groupby(["GW","element"],as_index=False).agg(actual_points=("total_points","sum"))
    a["name"]=a.element.map(names).fillna(a.element.astype(str));return a

def actual24(path):
    x=pd.read_csv(path)
    gw="gw" if "gw" in x.columns else "GW"
    a=x.groupby([gw,"element"],as_index=False).agg(actual_points=("total_points","sum"))
    a=a.rename(columns={gw:"GW"})
    namecol=next((c for c in ["name","web_name","player_name"] if c in x.columns),None)
    if namecol:
        nm=x.groupby([gw,"element"])[namecol].first().reset_index().rename(columns={gw:"GW",namecol:"name"})
        a=a.merge(nm,on=["GW","element"],how="left")
    else:a["name"]=a.element.astype(str)
    return a

def evaluate_season(season,root,prefix,actual,discount):
    decisions=[];traces=[]
    for vname,var in VARIANTS.items():
        for start,end in [(6,19),(20,38)]:
            d,t=replay_half(root,prefix,start,end,var,discount)
            d.update(season=season,variant=vname,half=f"{start}-{end}")
            t["season"]=season;t["variant"]=vname;t["half"]=f"{start}-{end}"
            decisions.append(d);traces.append(t)
    d=pd.DataFrame(decisions)
    d=d.merge(actual[["GW","element","actual_points"]],left_on=["gw","candidate_id"],right_on=["GW","element"],how="left").drop(columns=["GW","element"])
    return d,pd.concat(traces,ignore_index=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--origins24",required=True);ap.add_argument("--origins25",required=True)
    ap.add_argument("--actual24",required=True);ap.add_argument("--out",required=True)
    ap.add_argument("--discount",type=float,default=.97)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    d24,t24=evaluate_season("2024-25",Path(a.origins24),"tc24-origin-",actual24(a.actual24),a.discount)
    d25,t25=evaluate_season("2025-26",Path(a.origins25),"tc-origin-",actual25(),a.discount)
    d=pd.concat([d24,d25],ignore_index=True);t=pd.concat([t24,t25],ignore_index=True)

    totals=d.groupby("variant",as_index=False).agg(
      actual_tc_points=("actual_points","sum"),
      avg_actual_tc=("actual_points","mean"),
      avg_selected_mean=("mean","mean"),
      total_mean_sacrifice=("mean_sacrifice","sum"),
      avg_mean_sacrifice=("mean_sacrifice","mean"),
      changed_decisions=("mean_sacrifice",lambda x:int((x>1e-9).sum())),
    )
    base=d[d.variant.eq("mean")][["season","half","gw","candidate_id"]].rename(columns={"gw":"base_gw","candidate_id":"base_id"})
    cmp=d.merge(base,on=["season","half"],how="left")
    cmp["different_from_mean"]=(cmp.gw!=cmp.base_gw)|(cmp.candidate_id!=cmp.base_id)
    diffs=cmp.groupby("variant",as_index=False).different_from_mean.sum().rename(columns={"different_from_mean":"decision_changes_vs_mean"})
    totals=totals.merge(diffs,on="variant").sort_values(["total_mean_sacrifice","actual_tc_points"],ascending=[True,False])

    d.to_csv(out/"multiseason_decisions.csv",index=False);t.to_csv(out/"multiseason_traces.csv",index=False);totals.to_csv(out/"multiseason_totals.csv",index=False)
    summary={"classification":"TC multi-season upside sensitivity diagnostic","seasons":["2024-25 conditional","2025-26"],"discount":a.discount,
      "variants":VARIANTS,"warning":"2024/25 is conditional/training-overlap and actual points are hindsight diagnostics; do not tune solely to realised points.",
      "totals":totals.to_dict("records"),"decisions":d.to_dict("records")}
    (out/"summary.json").write_text(json.dumps(summary,indent=2,default=str)+"\n")
    print(totals.to_string(index=False));print(d.to_string(index=False))

if __name__=="__main__":main()
