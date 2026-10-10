#!/usr/bin/env python3
"""Bridge immutable FPL completed-GW files into cutoff-safe replay observations.

The output is a history *source* for the existing frozen pipeline, NOT a
certified forecast. It preserves per-fixture IDs and refuses aggregate fallback.
"""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data_v1_1/raw/fpl_2026_27_official_gw"
OUT=ROOT/"data_v1_1/derived/live_locked_inputs/2026-27-v1"

def rows_for_gameweek(payload, available_at):
    gw=int(payload["gw"])
    matches={int(f["id"]):f for f in payload["official_fixtures"]}
    if not matches: raise ValueError(f"GW{gw}: no fixtures")
    if not payload["official_event"]["finished"] or not payload["official_event"]["data_checked"]:
        raise ValueError(f"GW{gw}: not finalized")
    rows=[]
    unique=set()
    for player in payload["official_player_live"]:
        pid=int(player["id"])
        explanations=player.get("explain")
        if explanations is None:
            raise ValueError(f"GW{gw} player {pid}: missing per-fixture explain")
        # Every appearance record is attributed to an actual fixture. Zero-minute
        # no-appearance rows are filled only for the player's known club below
        # by an independent roster snapshot; never fabricate starts from minutes.
        for match in explanations:
            fid=int(match["fixture"])
            if fid not in matches: raise ValueError(f"GW{gw}: unknown fixture {fid}")
            key=(fid,pid)
            if key in unique: raise ValueError(f"GW{gw}: duplicate {key}")
            unique.add(key)
            stats=match.get("stats",[])
            metric={str(e["identifier"]):e["value"] for e in stats}
            # FPL explain.stats are *point explanations*, not guaranteed
            # per-fixture minutes or even complete player-match statistics.
            # Never convert their absence to zero observed minutes.
            minutes=metric.get("minutes")
            if minutes is not None and not 0<=int(minutes)<=120:
                raise ValueError(f"Invalid minutes for {key}")
            # Keep nullable and require a separate verified starter/minutes feed.
            rows.append(dict(season="2026-27",gw=gw,fixture_id=fid,
                             player_id=pid,minutes=int(minutes) if minutes is not None else None,
                             started=None,total_points=metric.get("total_points"),
                             point_explanations=metric,available_at=available_at))
    return rows

def build(source=RAW, destination=OUT, asof=None):
    paths=sorted(source.glob("gw[0-9][0-9].json"))
    if not paths: raise FileNotFoundError("No collected official GW files")
    all_rows=[];sources=[];seen=set()
    cutoff=(datetime.fromisoformat(asof.replace("Z","+00:00")) if asof else None)
    for path in paths:
        blob=path.read_bytes();p=json.loads(blob)
        gw=int(p["gw"])
        if path.name!=f"gw{gw:02d}.json":raise ValueError("GW filename mismatch")
        # Snapshot observation time provides a strict safe LOWER bound on
        # availability; never infer pre-cutoff validity from deadline alone.
        if cutoff:
            deadline=datetime.fromisoformat(p["official_event"]["deadline_time"].replace("Z","+00:00"))
            if deadline>=cutoff:raise ValueError(f"GW{gw} deadline is not before forecast cutoff")
        collected_at=p.get("observed_at_utc")
        if collected_at is None:
            raise ValueError(f"GW{gw}: snapshot lacks original observation timestamp")
        observed_at=datetime.fromisoformat(collected_at.replace("Z","+00:00"))
        if observed_at.tzinfo is None:
            raise ValueError(f"GW{gw}: snapshot observation timestamp has no timezone")
        if cutoff is not None and observed_at>=cutoff:
            raise ValueError(f"GW{gw}: observed data not available before forecast cutoff")
        new=rows_for_gameweek(p,observed_at.isoformat())
        for row in new:
            key=(row["fixture_id"],row["player_id"])
            if key in seen:raise ValueError(f"Duplicate across weeks: {key}")
            seen.add(key)
        all_rows+=new
        sources.append({"gw":gw,"path":path.name,"sha256":hashlib.sha256(blob).hexdigest(),
                        "rows_with_explain":len(new)})
    output={"classification":"OFFICIAL_FIXTURE_HISTORY_STAGING_NOT_CERTIFIED",
            "season":"2026-27","rows":all_rows,"sources":sources,
            "starts_certified":False,"available_at_certified":True,
            "full_roster_coverage_certified":False,
            "locked_model_active":False,
            "blocking_requirements":["source verified XI starters","nonappearance rows and role roster",
               "separate authoritative per-fixture minute and starter evidence",
               "stable player and fixture identity maps","provider performance coverage"]}
    destination.mkdir(parents=True,exist_ok=True)
    (destination/"official_completed_gw_staging.json").write_text(
        json.dumps(output,ensure_ascii=False,separators=(",",":"),allow_nan=False))
    return output

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,default=RAW)
    ap.add_argument("--out",type=Path,default=OUT)
    ap.add_argument("--asof")
    a=ap.parse_args()
    result=build(a.source,a.out,a.asof)
    print(json.dumps({"gws":[s["gw"] for s in result["sources"]],
       "fixture_player_rows":len(result["rows"]),
       "forecast_certified":False,"blockers":result["blocking_requirements"]}))
