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
    "mean": dict(kind="mean"),
    "mean_plus_025_q75_gap": dict(kind="qgap",lam=.25,q=.75),
    "mean_plus_050_q75_gap": dict(kind="qgap",lam=.50,q=.75),
    "mean_plus_1p_p10": dict(kind="tail",lam=1.0,thr=10.0),
    "mean_plus_2p_p10": dict(kind="tail",lam=2.0,thr=10.0),
    "mean_plus_2p_p15": dict(kind="tail",lam=2.0,thr=15.0),
    "mean_plus_4p_p15": dict(kind="tail",lam=4.0,thr=15.0),
}

def load_origin(root:Path,gw:int)->pd.DataFrame:
    hits=list(root.glob(f"**/*{gw}*/tc_samples.csv.gz"))
    if len(hits)!=1:
        raise RuntimeError(f"Expected one origin sample file for GW{gw}, got {hits}")
    return pd.read_csv(hits[0])

def player_stats(samples:pd.DataFrame,variant:dict)->pd.DataFrame:
    grp=samples.groupby(["gw","candidate_id","candidate_name"],sort=False).points
    s=grp.agg(mean="mean").reset_index()
    if variant["kind"]=="mean":
        s["score"]=s["mean"]
    elif variant["kind"]=="qgap":
        q=float(variant["q"]);lam=float(variant["lam"])
        qq=grp.quantile(q).rename("q").reset_index()
        s=s.merge(qq,on=["gw","candidate_id","candidate_name"],how="left")
        s["score"]=s["mean"]+lam*(s["q"]-s["mean"])
    elif variant["kind"]=="tail":
        thr=float(variant["thr"]);lam=float(variant["lam"])
        p=grp.apply(lambda x: float((x>=thr).mean())).rename("tail_p").reset_index()
        s=s.merge(p,on=["gw","candidate_id","candidate_name"],how="left")
        s["score"]=s["mean"]+lam*s["tail_p"]
    else:
        raise ValueError(variant)
    return s

def timing_distribution(samples:pd.DataFrame,variant:dict,current_gw:int,end_gw:int,discount:float):
    stats=player_stats(samples,variant)
    idx=stats.groupby("gw",sort=True).score.idxmax()
    chosen=stats.loc[idx].copy().sort_values("gw")
    chosen["offset"]=chosen.gw-current_gw
    chosen["adjusted_score"]=chosen.score*np.power(discount,chosen.offset)

    # Probability diagnostic: fix the selected player in each GW ex ante,
    # then ask which GW wins each Monte Carlo world after horizon discount.
    fixed=samples.merge(chosen[["gw","candidate_id"]],on=["gw","candidate_id"],how="inner")
    fixed["adjusted_points"]=fixed.points*np.power(discount,fixed.gw-current_gw)
    fixed=fixed.sort_values(["simulation","adjusted_points","gw"],ascending=[True,False,True])
    winners=fixed.groupby("simulation",sort=False).head(1)
    n=int(fixed.simulation.nunique())
    probs=winners.gw.value_counts().to_dict()
    chosen["probability_best"]=[float(probs.get(int(g),0)/n) for g in chosen.gw]
    return chosen

def replay_half(root,start,end,variant,discount):
    trace=[];decision=None
    for gw in range(start,end+1):
        samples=load_origin(root,gw)
        chosen=timing_distribution(samples,variant,gw,end,discount)
        cur=chosen[chosen.gw.eq(gw)].iloc[0]
        future=chosen[chosen.gw.gt(gw)]
        save=0.0 if future.empty else float(future.adjusted_score.max())
        edge=float(cur.score-save)
        use=(gw==end) or edge>=0
        trace.append(dict(
            gw=gw,candidate_id=int(cur.candidate_id),candidate_name=str(cur.candidate_name),
            candidate_mean=float(cur["mean"]),candidate_score=float(cur.score),
            probability_current_gw_best=float(cur.probability_best),
            save_option_score=save,use_edge=edge,action="USE_TC" if use else "SAVE_TC",
        ))
        if use:
            decision=trace[-1].copy();break
    if decision is None:raise RuntimeError("No decision")
    return decision,pd.DataFrame(trace)

def actual_table():
    gws=hp.unpack_runtime("merged_gw.csv")
    raw=hp.unpack_runtime("players_raw.csv").drop_duplicates("id")
    names=raw.set_index("id").web_name.astype(str).to_dict()
    a=gws.groupby(["GW","element"],as_index=False).agg(
        actual_points=("total_points","sum"),actual_minutes=("minutes","sum")
    )
    a["name"]=a.element.map(names).fillna(a.element.astype(str))
    return a

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--origins",required=True)
    ap.add_argument("--out",required=True)
    ap.add_argument("--discount",type=float,default=.97)
    a=ap.parse_args()
    root=Path(a.origins);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    actual=actual_table()

    decisions=[];traces=[]
    for name,var in VARIANTS.items():
        for start,end in [(6,19),(20,38)]:
            d,t=replay_half(root,start,end,var,a.discount)
            d.update(variant=name,half=f"{start}-{end}")
            t["variant"]=name;t["half"]=f"{start}-{end}"
            decisions.append(d);traces.append(t)

    dec=pd.DataFrame(decisions)
    dec=dec.merge(
        actual[["GW","element","actual_points","actual_minutes"]],
        left_on=["gw","candidate_id"],right_on=["GW","element"],how="left"
    ).drop(columns=["GW","element"])
    dec["actual_tc_added_points"]=dec.actual_points
    totals=dec.groupby("variant",as_index=False).agg(
        tc_added_points=("actual_tc_added_points","sum"),
        mean_selected_forecast=("candidate_mean","mean"),
        mean_selected_score=("candidate_score","mean")
    ).sort_values("tc_added_points",ascending=False)

    # Candidate-level audit at each selected GW: actual rank among ex-ante top-20.
    audits=[]
    for r in dec.itertuples(index=False):
        samples=load_origin(root,int(r.gw))
        stats=player_stats(samples,VARIANTS[str(r.variant)])
        g=stats[stats.gw.eq(int(r.gw))].copy()
        g=g.merge(actual[actual.GW.eq(int(r.gw))][["element","actual_points"]],
                  left_on="candidate_id",right_on="element",how="left")
        g["variant"]=r.variant;g["half"]=r.half;g["selected"]=g.candidate_id.eq(int(r.candidate_id))
        audits.append(g.sort_values("score",ascending=False).head(20))
    audit=pd.concat(audits,ignore_index=True)

    dec.to_csv(out/"variant_decisions.csv",index=False)
    pd.concat(traces,ignore_index=True).to_csv(out/"variant_traces.csv",index=False)
    totals.to_csv(out/"variant_totals.csv",index=False)
    audit.to_csv(out/"selected_gw_candidate_audit.csv",index=False)
    summary={
        "classification":"TC upside sensitivity experiment; not a locked model selection",
        "discount":float(a.discount),
        "variants":VARIANTS,
        "note":"Actual TC points are diagnostic hindsight only; do not choose a variant solely by realised 2025/26 points.",
        "totals":totals.to_dict("records"),
        "decisions":dec.to_dict("records"),
    }
    (out/"summary.json").write_text(json.dumps(summary,indent=2,default=str)+"\n")
    print(json.dumps(summary,indent=2,default=str))

if __name__=="__main__":
    main()
