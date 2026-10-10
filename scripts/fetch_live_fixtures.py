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
    obj={"source":"Official Fantasy Premier League public API","fetched_at":datetime.now(timezone.utc).isoformat(),
         "season":bootstrap.get("events",[{}])[0].get("deadline_time","")[:4],
         "teams":teams,"fixtures":clean}
    path=ROOT/"app"/"live-fixtures.json"
    path.write_text(json.dumps(obj,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print("Official fixtures fetched:",len(clean))
if __name__=="__main__":main()
