#!/usr/bin/env python3
"""Publish strictly labelled *diagnostic* locked-MM minutes to the static app.

Uses the existing frozen inference and approved hard-availability release
boundary, but does not certify historical reconstructed training / PM / TS /
chips. Never touches app/final-forecast.json or locked_model_active.
"""
from __future__ import annotations
import json,sys,math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.live_availability_boundary import prepare_live_mm_release_candidate

WORK=ROOT/'work/live-final-model'
APP=ROOT/'app'

def publish():
    audit=json.loads((WORK/'mm_inference_one_gw.json').read_text())
    if audit.get("live_certified") is not False or audit.get("target_outcomes_used")!=0:
        raise ValueError("This page must not publish a purported certified or leaking MM")
    source=json.loads((WORK/'source_manifest.json').read_text())
    raw=pd.read_csv(WORK/'mm_frozen_diagnostic_one_gw.csv.gz',low_memory=False)
    if raw.empty or raw.fpl_element.isna().any() or raw.fpl_element.duplicated().any():
        raise ValueError("Missing / duplicate stable player identity in diagnostic MM")
    gw=int(source["target_gw"])
    if not raw.gw.eq(gw).all() or not raw.target_gw.eq(gw).all():
        raise ValueError("Diagnostic preview may only use current GW scoped news")
    gated=prepare_live_mm_release_candidate(
        raw,p_start=raw.p_start.to_numpy(float),
        q_sub=raw.mm_q_sub.to_numpy(float),
        sub_minutes=raw.mm_sub_minutes.to_numpy(float),
        origin_gw=gw,news_scoped_gw=gw)
    n=667
    if len(gated)!=n or gated.team_id.nunique()!=20:
        raise ValueError("Incomplete 20-team/667-player checkpoint")
    grouped=gated.groupby(["fixture_uuid","team_id"]).p_start.sum()
    if (grouped-11).abs().max()>1e-6:
        raise ValueError("Exact eleven starter constraint failed")
    if not np.isfinite(gated[["p_start","mm_q_sub","mm_raw_xmins","xmins"]].to_numpy(float)).all():
        raise ValueError("Non-finite MM output")
    summaries=[]
    for r in gated.itertuples(index=False):
        hard=bool(r.live_eligibility_applied)
        summaries.append({
          "id":int(r.fpl_element),"name":str(r.player),
          "team_id":int(r.team_id),"team":str(r.team),"role":str(r.expected_role),
          "xi_role":str(r.xi_assigned_role),"xi_formation":str(r.xi_formation),
          "p_start":round(float(r.p_start),6),
          "p_sub_given_not_start":round(float(r.live_effective_q_sub),6),
          "xmins":round(float(r.xmins),4),
          "raw_xmins":round(float(r.mm_raw_xmins),4),
          "availability_state":str(r.team_news_state),
          "not_available":hard
        })
    summaries.sort(key=lambda x:x["id"])
    source_asof=str(source["observed_at"])
    report={
      "schema_version":1,
      "classification":"UNCERTIFIED_DIAGNOSTIC_FROZEN_MM_NOT_LIVE_FINAL",
      "locked_model_active":False,
      "full_final_chain_certified":False,
      "model_math_changed":False,
      "gw":gw,
      "player_count":len(summaries),"fixture_count":int(raw.fixture_uuid.nunique()),
      "team_count":20,"source_observed_at":source_asof,
      "training_status":str(audit["training_quality"]["classification"]),
      "historical_training_blockers":audit["training_quality"]["blockers"],
      "original_exact11_max_error":float(audit["exact11_max_error"]),
      "availability_rule":"live-hard-eligibility-v1",
      "not_available_count":int(gated.live_eligibility_applied.sum()),
      "description":"Låst MM-kode på rekonstrueret GW1-5 historik; diagnostik, IKKE en certificeret live-finalmodel eller PM-xP.",
      "rows":summaries}
    APP.mkdir(parents=True,exist_ok=True)
    (APP/'mm-diagnostic.json').write_text(json.dumps(report,ensure_ascii=False,separators=(',',':'),allow_nan=False))
    print('PUBLISHED CLEARLY UNCERTIFIED MM DIAGNOSTIC',
          json.dumps({k:report[k] for k in ('gw','player_count','fixture_count','not_available_count','source_observed_at','classification')}))
    return report

if __name__=="__main__":publish()
