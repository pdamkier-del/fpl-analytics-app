"""Public role and availability view, with strict separation from frozen MM outputs."""
import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"app"
def main():
    d=json.loads((APP/"current-players.json").read_text(encoding="utf-8"))
    teams=d["teams"];players=d["players"]
    result={"schema_version":1,"generated_at":datetime.now(timezone.utc).isoformat(),
      "official_data_asof":d["fetched_at"],"source":"Official FPL bootstrap",
      "locked_mm_applied":False,"expected_xi_certified":False,
      "explanation":"Official FPL positional class and availability only. A tactical role or expected XI requires verified locked model output.",
      "teams":[]}
    for key,t in sorted(teams.items(),key=lambda x:x[1]["name"]):
        squad=[p for p in players if str(p["team"])==str(key)]
        result["teams"].append({"id":int(key),"name":t["name"],"short_name":t["short_name"],
          "players":[{"id":p["id"],"name":p["web_name"],"position":d["positions"].get(str(p["position"]),"Unknown"),
            "status":p.get("status"),"chance_of_playing_next_round":p.get("chance_of_playing_next_round"),
            "tactical_role":None,"p_start":None} for p in squad]})
    (APP/"role-status.json").write_text(json.dumps(result,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    assert len(result["teams"])>=18
    assert sum(len(t["players"]) for t in result["teams"])>=300
    assert all(p["tactical_role"] is None and p["p_start"] is None for t in result["teams"] for p in t["players"])
    print("Role availability contract verified:",len(result["teams"]),"teams")
if __name__=="__main__":main()
