#!/usr/bin/env python3
"""Capture the official FPL fixture schedule at update time.

Every publish creates a timestamped snapshot of the official FPL fixtures and
bootstrap team map. The snapshot is the cutoff-safe record of what the FPL API
actually exposed at that point in time.
"""
from __future__ import annotations

import csv
import json
import shutil
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data_v1_1" / "derived" / "fpl_schedule_knowledge" / "live"
SNAPSHOTS = OUT / "snapshots"
FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"
BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"

CHANGE_FIELDS = [
    "observed_at_utc", "fixture_id", "home_team", "away_team",
    "old_event", "new_event", "old_kickoff_time", "new_kickoff_time",
]


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "fpl-analytics-app schedule snapshot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def build_schedule(fixtures: list[dict], teams: list[dict]) -> dict:
    team_names = {int(t["id"]): str(t["name"]) for t in teams}
    ids = sorted(team_names)
    counts = defaultdict(lambda: defaultdict(int))
    compact = []
    for f in fixtures:
        event = f.get("event")
        home = int(f["team_h"])
        away = int(f["team_a"])
        if event is not None:
            event = int(event)
            counts[event][home] += 1
            counts[event][away] += 1
        compact.append({
            "id": int(f["id"]), "event": event, "team_h": home, "team_a": away,
            "home_team": team_names.get(home, str(home)),
            "away_team": team_names.get(away, str(away)),
            "kickoff_time": f.get("kickoff_time"),
            "started": bool(f.get("started", False)),
            "finished": bool(f.get("finished", False)),
        })

    event_status = []
    for event in range(1, 39):
        dgw, bgw = [], []
        for tid in ids:
            n = counts[event].get(tid, 0)
            if n == 0:
                bgw.append(team_names[tid])
            elif n > 1:
                dgw.append({"team": team_names[tid], "fixtures": n})
        event_status.append({"event": event, "dgw_teams": dgw, "bgw_teams": bgw})
    return {"fixtures": sorted(compact, key=lambda x: x["id"]), "event_status": event_status}


def previous_snapshot(current_path: Path):
    candidates = sorted(p for p in SNAPSHOTS.glob("*.json") if p != current_path)
    return candidates[-1] if candidates else None


def append_changes(observed_at: str, old: dict | None, new: dict) -> int:
    if not old:
        return 0
    before = {int(f["id"]): f for f in old.get("fixtures", [])}
    rows = []
    for f in new.get("fixtures", []):
        fid = int(f["id"])
        p = before.get(fid)
        if not p:
            continue
        if p.get("event") == f.get("event") and p.get("kickoff_time") == f.get("kickoff_time"):
            continue
        rows.append({
            "observed_at_utc": observed_at, "fixture_id": fid,
            "home_team": f.get("home_team"), "away_team": f.get("away_team"),
            "old_event": p.get("event"), "new_event": f.get("event"),
            "old_kickoff_time": p.get("kickoff_time"), "new_kickoff_time": f.get("kickoff_time"),
        })
    if not rows:
        return 0
    path = OUT / "changes.csv"
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CHANGE_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main():
    now = datetime.now(timezone.utc)
    observed_at = now.isoformat().replace("+00:00", "Z")
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    fixtures = fetch_json(FIXTURES_URL)
    bootstrap = fetch_json(BOOTSTRAP_URL)
    season_start = now.year if now.month >= 7 else now.year - 1
    season = f"{season_start}-{str(season_start + 1)[-2:]}"
    upcoming = next((int(e["id"]) for e in bootstrap.get("events", [])
                     if e.get("is_next")), None)
    if upcoming is None:
        upcoming = next((int(e["id"]) for e in bootstrap.get("events", [])
                         if not e.get("finished")), None)
    # Preserve the observable official statuses and timing separately from xP.
    official_players = [
        {"id": int(p["id"]), "name": p.get("web_name"),
         "status": p.get("status"), "chance_next_round": p.get("chance_of_playing_next_round"),
         "news": p.get("news"), "price_tenths": p.get("now_cost"),
         "team_id": p.get("team"), "element_type": p.get("element_type"),
         "player_code": p.get("code")}
        for p in bootstrap.get("elements", []) if p.get("id") is not None
    ]
    payload = {"schema_version": 2, "season": season, "observed_at_utc": observed_at,
               "official_next_gw": upcoming,
               "sources": {"fixtures": FIXTURES_URL, "bootstrap": BOOTSTRAP_URL},
               "players": official_players,
               "teams": [{"id": int(t["id"]), "code": t.get("code"),
                          "name": t.get("name"), "short_name": t.get("short_name")}
                         for t in bootstrap.get("teams", [])],
               **build_schedule(fixtures, bootstrap["teams"])}
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    current = SNAPSHOTS / f"{stamp}.json"
    prev = previous_snapshot(current)
    old_payload = json.loads(prev.read_text(encoding="utf-8")) if prev else None
    current.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    shutil.copyfile(current, OUT / "latest.json")
    changed = append_changes(observed_at, old_payload, payload)
    dgw_events = [{"event": x["event"], "teams": x["dgw_teams"]} for x in payload["event_status"] if x["dgw_teams"]]
    bgw_events = [{"event": x["event"], "teams": x["bgw_teams"]} for x in payload["event_status"] if x["bgw_teams"]]
    print(json.dumps({"snapshot": str(current.relative_to(ROOT)),
                      "previous_snapshot": str(prev.relative_to(ROOT)) if prev else None,
                      "schedule_changes": changed, "dgw_events": dgw_events, "bgw_events": bgw_events},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
