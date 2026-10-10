"""Collect public FPL player-by-gameweek history for *completed* 2026/27 GWs.

Historical outcomes are allowed for games that finished before the prediction
cutoff. No future event live results are queried. This is source evidence,
not a locked MM output.
"""
from __future__ import annotations
import json,time
from urllib.request import Request,urlopen
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];APP=ROOT/"app"
FIELDS=("minutes","starts","total_points","goals_scored","assists","expected_goals",
        "expected_assists","expected_goal_involvements","expected_goals_conceded",
        "clean_sheets","saves","bonus","bps","yellow_cards","red_cards")
def load(gw):
    url=f"https://fantasy.premierleague.com/api/event/{gw}/live/"
    for attempt in range(3):
        try:
            with urlopen(Request(url,headers={"Accept":"application/json",
                    "User-Agent":"FPLAnalytics/1.0"}),timeout=30) as response:
                return json.load(response)
        except Exception:
            if attempt==2:raise
            time.sleep(2*(attempt+1))
def main():
    official=json.loads((APP/"current-players.json").read_text())
    fixtures=json.loads((APP/"live-fixtures.json").read_text())
    gw=official.get("next_gw")
    if not isinstance(gw,int):raise ValueError("Missing official next GW")
    complete=[n for n in range(1,gw) if
       any(f.get("gw")==n for f in fixtures["fixtures"]) and
       all(f["finished"] for f in fixtures["fixtures"] if f.get("gw")==n)]
    current_ids={p["id"] for p in official["players"]}
    records=[]
    for n in complete:
        event=load(n)
        rows=event.get("elements") or []
        if len(rows)<250:raise ValueError(f"GW{n}: incomplete live player feed")
        for row in rows:
            player_id=row.get("id")
            if player_id not in current_ids:continue
            stats=row.get("stats") or {}
            records.append({"player_id":player_id,"gw":n,
                **{k:stats.get(k) for k in FIELDS}})
        print(f"OFFICIAL FPL GW{n} history: {len(rows)} elements",flush=True)
    if not complete:raise ValueError("No completed gameweeks; cannot build minutes recency history")
    if len(records)<250*len(complete):raise ValueError("Historical player coverage too small")
    out={"schema_version":1,"classification":"historical_official_fpl_per_gw_stats_not_frozen_mm",
         "observed_at":official["fetched_at"],"completed_gws":complete,
         "player_ids_in_current_snapshot":len(current_ids),
         "source":"FPL event/{gw}/live; only complete gameweeks before official next GW",
         "rows":records}
    (APP/"historical-gw-stats.json").write_text(json.dumps(out,ensure_ascii=False,separators=(",",":"),allow_nan=False))
    print("OFFICIAL GW HISTORY:",len(records),"rows, finished GWs",complete)
if __name__=="__main__":main()
