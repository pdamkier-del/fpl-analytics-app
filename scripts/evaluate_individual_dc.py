"""Leakage-safe offline DC propensity scoring against an existing forecast table.

Research-only. Requires each historical action's publication/known timestamp.
No automatic filling of missing DC counts, minutes, positions or player IDs.
"""
from __future__ import annotations
import argparse
import json
from collections import defaultdict
from pathlib import Path
import pandas as pd
from experimental_individual_dc_propensity import player_dc_propensity,projected_dc_mean

def score_history(history,forecasts,prior_minutes=900.,half_life_days=365.):
    required_history={"player_uuid","known_at","minutes","dc_count"}
    required_forecast={"player_uuid","cutoff","position","role_rate90",
                       "expected_minutes","actual_dc_count"}
    if not required_history.issubset(history.columns):
        raise ValueError("Missing history: "+str(sorted(required_history-set(history.columns))))
    if not required_forecast.issubset(forecasts.columns):
        raise ValueError("Missing forecast: "+str(sorted(required_forecast-set(forecasts.columns))))
    hist=history.copy();fc=forecasts.copy()
    for d,k in ((hist,"known_at"),(fc,"cutoff")):
        d[k]=pd.to_datetime(d[k],utc=True,errors="raise")
        if d[k].isna().any(): raise ValueError("Missing timestamps")
    if fc[["player_uuid","cutoff"]].duplicated().any():
        raise ValueError("Duplicate player-cutoff forecast")
    hist_by_player={key: group.to_dict("records") for key,group in hist.groupby("player_uuid")}
    out=[]
    for row in fc.itertuples(index=False):
        past=hist_by_player.get(row.player_uuid,[])
        pred=player_dc_propensity(past,row.cutoff.to_pydatetime(),float(row.role_rate90),
                                  prior_minutes=prior_minutes,half_life_days=half_life_days)
        mu=projected_dc_mean(pred["neutral_dc_rate90"],float(row.expected_minutes))
        actual=float(row.actual_dc_count)
        if pd.isna(actual) or actual<0 or not actual.is_integer():
            raise ValueError("Missing or invalid DC outcome")
        out.append({"player_uuid":row.player_uuid,"cutoff":str(row.cutoff),
                    "position":row.position,"expected_dc_count":mu,
                    "actual_dc_count":actual,"history_rows":pred["observations_used"]})
    result=pd.DataFrame(out)
    if result.empty: raise ValueError("No scoring rows")
    error=result.expected_dc_count-result.actual_dc_count
    summary={"classification":"RESEARCH_DC_COUNT_DIAGNOSTIC_NOT_HISTORICAL_CERTIFICATION",
             "rows":len(result),"count_mae":float(error.abs().mean()),
             "count_rmse":float((error.pow(2).mean())**.5),
             "historical_publication_verified":False,
             "requires_original_dc_baseline_for_comparative_result":True}
    return result,summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history",required=True)
    p.add_argument("--forecasts",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    preds,report=score_history(pd.read_csv(args.history),pd.read_csv(args.forecasts))
    dst=Path(args.out);dst.mkdir(parents=True,exist_ok=True)
    preds.to_csv(dst/"dc_predictions.csv",index=False)
    (dst/"dc_research_summary.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
