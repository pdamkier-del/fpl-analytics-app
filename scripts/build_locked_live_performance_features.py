#!/usr/bin/env python3
"""Bridge observed 2026/27 FotMob match stats into the FROZEN performance features.

Invokes unmodified run_v4_performance_rating_experiment.add_features().
Uses exact previously selected per-stat zero policy and rating-proxy formula.
Unavailable raw provider fields are audited rather than silently described as
complete. No future stats or forecast label may enter this derivation.
"""
from __future__ import annotations
import gzip,json,sys
from collections import Counter
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_v4_performance_rating_experiment import add_features,RECENT_FEATURES
from live_provider_stat_evidence import raw_evidence

BASE=ROOT/"data_v1_1/derived/live_locked_inputs/2026-27-v1"
SEQ=BASE/"sequence_feature_matrix.csv.gz"
EVENTS=ROOT/"work/live-final-model/player_match_events.jsonl.gz"
OUT=BASE/"performance_feature_matrix.csv.gz"
AUDIT=ROOT/"work/live-final-model/live_performance_provenance.json"
PROVIDER_ALIASES={
  "xg":"expected_goals",
  "xa":"expected_assists",
  "shots_on_target":"ShotsOnTarget",
  "successful_dribbles":"dribbles_succeeded",
  "blocks":"shot_blocks",
}
# We intentionally do not map mixed or ambiguous fields such as accurate_passes
# (raw value can be completions/attempts rather than a percent).
NUM=["minutes_played","goals","assists","xg","xa","shots_on_target",
     "chances_created","successful_dribbles","tackles_won","interceptions",
     "recoveries","blocks","clearances","accurate_passes_percent",
     "saves","goals_prevented","goals_conceded","dispossessed"]

def build(target=None, persist=True):
    if not SEQ.is_file() or not EVENTS.is_file():
        raise FileNotFoundError("Restore live source checkpoint and build frozen sequence first")
    target=pd.read_csv(SEQ,low_memory=False) if target is None else target.copy()
    observations=[json.loads(row) for row in gzip.decompress(EVENTS.read_bytes()).splitlines()]
    if not observations:raise ValueError("No observed provider player match statistics")
    passing=raw_evidence(ROOT/"data_v1_1/raw/live-captures")
    passing_used=[]
    past=[];nonempty={k:0 for k in NUM};stats_keys=Counter()
    for row in observations:
        if not row.get("player_uuid") or not row.get("match_id"):
            continue
        val=row.get("stats") or {}
        if not isinstance(val,dict):raise ValueError("Invalid raw provider statistics")
        stats_keys.update(k for k,v in val.items() if v is not None and str(v).strip())
        p={"player_uuid":str(row["player_uuid"]),
           "match_id":str(row["match_id"]),
           "available_at":row.get("available_at")}
        for k in NUM:
            # Same old-model numeric missing-stat fallback as build_perf_ledger.
            v=val.get(k)
            if v is None and k in PROVIDER_ALIASES:
                v=val.get(PROVIDER_ALIASES[k])
            if k=="accurate_passes_percent" and v is None:
                key=(str(row["match_id"]).rsplit("-",1)[-1],str(row.get("provider_player_id")))
                evidence=passing.get(key)
                if evidence is not None:
                    v=evidence["value"]
                    passing_used.append({"match_id":row["match_id"],"player_uuid":row["player_uuid"],**evidence})
            if k=="minutes_played":
                v=row.get("minutes_played",v)
            if v is not None and str(v).strip():
                nonempty[k]+=1
            p[k]=v
        past.append(p)
    ledger=pd.DataFrame(past)
    ledger["available_at"]=pd.to_datetime(ledger.available_at,utc=True,errors="raise")
    cuts=pd.to_datetime(target.cutoff,utc=True,errors="raise")
    assert cuts.notna().all()
    if (ledger.available_at>=cuts.max()).any():
        # Completed matches after the initial source cutoff must be excluded,
        # not carried backward into this as-of forecast.
        ledger=ledger.loc[ledger.available_at<cuts.max()].copy()

    if ledger.duplicated(["player_uuid","match_id"]).any():
        raise ValueError("Duplicate provider player/match performance evidence")
    for k in NUM:
        ledger[k]=pd.to_numeric(ledger[k],errors="coerce").fillna(0.)
    ledger=ledger.loc[ledger.minutes_played>0].copy()

    ledger["goal_assist"]=ledger.goals+ledger.assists
    ledger["xgi"]=ledger.xg+ledger.xa
    ledger["def_actions"]=(ledger.tackles_won+ledger.interceptions+ledger.recoveries+
                           ledger.blocks+ledger.clearances)
    ledger["gk_actions"]=ledger.saves
    ledger["rating_proxy"]=(4*ledger.goals+3*ledger.assists+
            1.5*ledger.xg+1.2*ledger.xa+.25*ledger.shots_on_target+
            .15*ledger.chances_created+.08*ledger.def_actions+
            .20*ledger.saves+.70*ledger.goals_prevented-
            .30*ledger.goals_conceded-.10*ledger.dispossessed)
    keep=["player_uuid","match_id","available_at","minutes_played",
          "goal_assist","xgi","shots_on_target","chances_created",
          "successful_dribbles","def_actions","accurate_passes_percent",
          "gk_actions","goals_prevented","goals_conceded",
          "dispossessed","rating_proxy"]
    ledger=ledger[keep].sort_values(["player_uuid","available_at","match_id"])
    result=add_features(target,ledger)
    if not set(RECENT_FEATURES).issubset(result):
        raise ValueError("Frozen performance output incomplete")
    if not np.isfinite(result[RECENT_FEATURES].to_numpy(float)).all():
        raise ValueError("Frozen performance features nonfinite")
    if len(result)!=len(target) or result.duplicated(["fixture_uuid","player_uuid"]).any():
        raise ValueError("Frozen performance bridge damaged live identity")
    if persist and any(k in result for k in ("y","outcome_known_at","minutes")):
        raise ValueError("Future target labels must not be emitted")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    if persist: result.to_csv(OUT,index=False,compression="gzip")
    report={
        "status":"observed_performance_derived_not_locked_live_MM_inference",
        "origin_gw":int(target.gw.iloc[0]),
        "source_player_event_rows":len(observations),
        "usable_player_event_rows":len(ledger),
        "frozen_performance_feature_count":len(RECENT_FEATURES),
        "target_player_fixture_rows":len(result),
        "targets_with_prior_perf_history":int((result.perf_hist_n>0).sum()),
        "provider_fields_observed_counts":nonempty,
        "explicit_same_semantics_provider_aliases":PROVIDER_ALIASES,
        "raw_provider_stat_keys_top50":stats_keys.most_common(50),
        "passing_fraction_evidence_rows":len(passing_used),
        "unverified_tackle_alias":"matchstats.headers.tackles is not silently equated to tackles_won",
        "missing_stat_policy":"Exact historical frozen build_perf_ledger: missing numeric fields -> 0",
        "target_or_future_outcomes_used":0,
    }
    AUDIT.parent.mkdir(parents=True,exist_ok=True)
    if persist: AUDIT.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    if persist: (AUDIT.parent/"live_passing_evidence.json").write_text(json.dumps(passing_used,indent=2)+"\n")
    print("FROZEN LIVE PERFORMANCE FEATURES",json.dumps(report),flush=True)
    return result
if __name__=="__main__":build()

