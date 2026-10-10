#!/usr/bin/env python3
"""Collect immutable official completed-GW FPL snapshots for rolling live forecasts.

This ingests observations, NOT a certified model forecast. No unfinished GW is
promoted; reruns are idempotent and fail on differing historical observations.
FPL's endpoint is live, so available_at is ingestion time, NOT game-time.
For cutoff-safe replays, retain the original predeadline snapshots separately.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data_v1_1" / "raw" / "fpl_2026_27_official_gw"
API = "https://fantasy.premierleague.com/api"
HEADERS = {"User-Agent": "FPL-Analytics-2026-weekly-observation-collector"}

def get_json(session, endpoint):
    response = session.get(API + endpoint, headers=HEADERS, timeout=35)
    response.raise_for_status()
    return response.json()

def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")

def collect(out=BASE):
    session = requests.Session()
    bootstrap = get_json(session, "/bootstrap-static/")
    events = bootstrap["events"]
    fixture_rows = get_json(session, "/fixtures/")
    fixtures_by_gw = {}
    for row in fixture_rows:
        if row.get("event") is not None:
            fixtures_by_gw.setdefault(int(row["event"]), []).append(row)
    now = datetime.now(timezone.utc).isoformat()
    out.mkdir(parents=True, exist_ok=True)
    collected, skipped = [], []
    for event in events:
        gw = int(event["id"])
        if not event.get("finished", False) or not event.get("data_checked", False):
            skipped.append(gw)
            continue
        matches = fixtures_by_gw.get(gw, [])
        if not matches or any(not match.get("finished") for match in matches):
            skipped.append(gw)
            continue
        # Official FPL gameweek live endpoint carries per-player historical
        # minutes, starts (where supplied), points and gameweek event statistics.
        live = get_json(session, f"/event/{gw}/live/")
        raw_elements = live.get("elements", [])
        # FPL may return keyed player IDs instead of a list of player objects.
        # Normalize without dropping the original player identity.
        if isinstance(raw_elements, dict):
            elements = []
            for player_id, info in raw_elements.items():
                if not isinstance(info, dict):
                    raise ValueError(f"GW{gw}: invalid player {player_id}")
                item = dict(info)
                if "id" in item and int(item["id"]) != int(player_id):
                    raise ValueError(f"GW{gw}: conflicting player ID {player_id}")
                item["id"] = int(player_id)
                elements.append(item)
            elements.sort(key=lambda x: int(x["id"]))
        elif isinstance(raw_elements, list):
            elements = raw_elements
        else:
            raise ValueError(f"GW{gw}: unexpected FPL player payload")
        if not elements:
            raise ValueError(f"GW{gw}: no official player observations")
        ids = [int(e["id"]) for e in elements]
        if len(ids) != len(set(ids)):
            raise ValueError(f"GW{gw}: duplicated player IDs")
        fixture_ids = [int(f["id"]) for f in matches]
        if len(fixture_ids) != len(set(fixture_ids)):
            raise ValueError(f"GW{gw}: duplicated fixture IDs")
        payload = {
            "season": "2026-27", "gw": gw, "observed_at_utc": now,
            "official_event": {"id":gw, "deadline_time":event["deadline_time"],
                               "finished":True,"data_checked":True},
            "official_fixtures": matches, "official_player_live": elements,
        }
        data = canonical(payload)
        path = out / f"gw{gw:02d}.json"
        digest = hashlib.sha256(data).hexdigest()
        if path.exists():
            previous = json.loads(path.read_bytes())
            # Only observation timestamp is transient. A completed GW must not
            # silently change stats: any provider revision needs explicit review.
            prior = {k:v for k,v in previous.items() if k != "observed_at_utc"}
            current = {k:v for k,v in payload.items() if k != "observed_at_utc"}
            if prior != current:
                raise ValueError(f"GW{gw}: immutable snapshot changed; review source revision explicitly")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            path.write_bytes(data)
        collected.append({"gw": gw, "sha256": digest,
                          "player_rows": len(elements),
                          "fixtures": len(matches)})
    existing = sorted(out.glob("gw[0-9][0-9].json"))
    manifest = {
        "kind": "official_completed_gw_ingestion_only_not_forecast",
        "season": "2026-27", "collected_at_utc": now,
        "completed_gws": collected, "skipped_unfinished_gws": skipped,
        "stored_files": [p.name for p in existing],
        "cutoff_safe_replay": False, "locked_model_active": False,
        "note": "Live endpoint retrieval is NOT proof of as-of availability. No model prediction permitted without downstream temporal and feature audits."
    }
    (out / "ingestion_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"completed": [r["gw"] for r in collected],
                      "skipped": skipped, "saved": len(existing),
                      "model_certified": False}))
    return manifest

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=BASE)
    args = parser.parse_args()
    collect(args.out)
