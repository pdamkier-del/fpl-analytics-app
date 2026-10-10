"""Build the reproducible *official-only* one-GW player/fixture source layer.

This is an input staging artifact, NOT the frozen MM/PM feature matrix.
Never imports future match outcomes or uses FPL's ep_next as a model target.
"""
from __future__ import annotations
import json,hashlib
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"app"
OUT=APP/"gw-source-features.json"

def main():
    raw_players=(APP/"current-players.json").read_bytes()
    raw_fixtures=(APP/"live-fixtures.json").read_bytes()
    people=json.loads(raw_players); games=json.loads(raw_fixtures)
    assert people["fetched_at"]==games["fetched_at"]
    gw=people["next_gw"]
    assert isinstance(gw,int) and 1<=gw<=38
    upcoming=sorted([f for f in games["fixtures"] if f["gw"]==gw and not f["finished"]],key=lambda f:f["id"])
    assert upcoming,"No unplayed fixtures for official next GW"
    history=json.loads((APP/"historical-gw-stats.json").read_text())
    assert history["observed_at"]==people["fetched_at"]
    assert all(hgw<gw for hgw in history["completed_gws"])
    by_player_history={}
    for h in history["rows"]:
        if h["gw"]>=gw:raise ValueError("Future historical stats detected")
        by_player_history.setdefault(int(h["player_id"]),[]).append(h)
    for group in by_player_history.values():group.sort(key=lambda x:x["gw"])
    members={}
    for p in people["players"]:
        members.setdefault(int(p["team"]),[]).append(p)
    observations=[]
    fixture_index=set()
    for f in upcoming:
        for home in (True,False):
            team=int(f["home"] if home else f["away"])
            rival=int(f["away"] if home else f["home"])
            for p in members[team]:
                key=(int(f["id"]),int(p["id"]))
                assert key not in fixture_index
                fixture_index.add(key)
                observations.append({
                    "fixture_id":int(f["id"]),"target_gw":gw,
                    "kickoff_utc":f["kickoff"],"player_id":int(p["id"]),
                    "player_code":p.get("code"),"team_id":team,"opponent_id":rival,
                    "home":home,"position":int(p["position"]), "status":p.get("status"),
                    "chance_next":p.get("chance_of_playing_next_round"),
                    "price":p.get("price"),"starts_to_cutoff":p.get("starts"),
                    "minutes_to_cutoff":p.get("minutes"),
                    "recent_finished_gws":by_player_history.get(int(p["id"]),[]),
                    "history_gws":len(by_player_history.get(int(p["id"]),[])),
                    "xg_to_cutoff":p.get("expected_goals"),
                    "xa_to_cutoff":p.get("expected_assists"),
                    "team_fixture_difficulty":f.get("difficulty_home" if home else "difficulty_away"),
                    "role_current_certified":False,"team_news_predeadline_certified":False,
                    "rating_current_certified":False
                })
    assert len(observations)>=250
    assert sum(bool(r["recent_finished_gws"]) for r in observations)>=250
    # A snapshot is inherently as-of: no future match results are present.
    assert all("score" not in k and "ep_next" not in k for row in observations for k in row)
    output={
        "schema_version":1,"classification":"official_asof_fixture_source_not_locked_MM_or_PM",
        "observed_at":people["fetched_at"],"gw":gw,"fixture_count":len(upcoming),
        "player_fixture_count":len(observations),
        "completed_history_gws":history["completed_gws"],
        "history_player_gw_rows":len(history["rows"]),
        "sha256":{"official_players":hashlib.sha256(raw_players).hexdigest(),
                  "official_fixtures":hashlib.sha256(raw_fixtures).hexdigest()},
        "certification":{"official_ids":True,"current_fixture_links":True,
                         "frozen_MM_feature_complete":False,"frozen_PM_feature_complete":False},
        "rows":observations
    }
    OUT.write_text(json.dumps(output,ensure_ascii=False,separators=(",",":"),allow_nan=False),encoding="utf-8")
    print("GW OFFICIAL SOURCE FEATURES:",gw,len(upcoming),"fixtures,",len(observations),"player-fixture rows; no MM/PM certification")
if __name__=="__main__":main()
