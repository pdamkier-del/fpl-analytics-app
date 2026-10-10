"""Fetch latest public FPL teams and fixtures for static GitHub Pages.

Independent from historic forecast model. Fail rather than relabel cached data as live.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
ROOT=Path(__file__).resolve().parents[1]
def get(name):
    req=Request("https://fantasy.premierleague.com/api/"+name,headers={"User-Agent":"FPLAnalytics/1.0","Accept":"application/json"})
    with urlopen(req,timeout=25) as response: return json.load(response)
def main():
    bootstrap=get("bootstrap-static/")
    fixtures=get("fixtures/")
    teams={t["id"]:{"name":t["name"],"short_name":t["short_name"],"code":t.get("code")} for t in bootstrap["teams"]}
    clean=[]
    for f in fixtures:
        clean.append({"id":f["id"],"gw":f.get("event"),"kickoff":f.get("kickoff_time"),
          "started":f.get("started",False),"finished":f.get("finished",False),
          "home":f["team_h"],"away":f["team_a"],"home_score":f.get("team_h_score"),
          "away_score":f.get("team_a_score"),"stats":f.get("stats") or []})
    next_event=next((e for e in bootstrap.get("events",[]) if e.get("is_next")),None)
    current_event=next((e for e in bootstrap.get("events",[]) if e.get("is_current")),None)
    obj={"source":"Official Fantasy Premier League public API","fetched_at":datetime.now(timezone.utc).isoformat(),
         "next_gw":next_event.get("id") if next_event else None,
         "current_gw":current_event.get("id") if current_event else None,
         "season":bootstrap.get("events",[{}])[0].get("deadline_time","")[:4],
         "teams":teams,"fixtures":clean}
    path=ROOT/"app"/"live-fixtures.json"
    path.write_text(json.dumps(obj,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    # Official current-season player identities. Tactical sub-roles are not in this feed.
    players=[{"id":x["id"],"web_name":x["web_name"],"first_name":x.get("first_name"),
       "second_name":x.get("second_name"),"team":x["team"],"position":x["element_type"],
       "code":x.get("code"),"photo":x.get("photo"),"status":x.get("status"),
       "chance_of_playing_next_round":x.get("chance_of_playing_next_round"),
       "price":x.get("now_cost",0)/10,"form":x.get("form"),"total_points":x.get("total_points"),"ep_this":x.get("ep_this"),"ep_next":x.get("ep_next"),"minutes":x.get("minutes"),"selected_by_percent":x.get("selected_by_percent")}
       for x in bootstrap["elements"]]
    positions={str(x["id"]):x["singular_name_short"] for x in bootstrap["element_types"]}
    directory={"source":obj["source"],"fetched_at":obj["fetched_at"],"next_gw":obj["next_gw"],"current_gw":obj["current_gw"],"teams":teams,
       "positions":positions,"players":players,
       "note":"FPL position GK/DEF/MID/FWD is official; detailed tactical roles and projected XI not verified."}
    (ROOT/"app"/"current-players.json").write_text(
        json.dumps(directory,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print("Official player identities:",len(players))
    print("Official fixtures fetched:",len(clean))
if __name__=="__main__":main()
