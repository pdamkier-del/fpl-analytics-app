"""Adapt verified current FPL IDs to the existing frozen historical role engine.

Does not infer the current tactical XI or run the locked minutes model.
"""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from build_live_role_snapshot import build

def main():
    source=json.loads((ROOT/"app"/"current-players.json").read_text(encoding="utf-8"))
    official={
      "observed_at_utc":source["fetched_at"],
      "season":"2026/27",
      "official_next_gw":None,
      "teams":[{"id":int(k),"code":v["code"],"short_name":v["short_name"]}
               for k,v in source["teams"].items() if v.get("code") is not None],
      "players":[{"id":int(p["id"]),"player_code":p["code"],
                  "team_id":int(p["team"]),"name":p["web_name"]}
                 for p in source["players"] if p.get("code") is not None]
    }
    bridge=json.loads((ROOT/"model"/"base_data.json").read_text(encoding="utf-8"))
    result=build(official,bridge)
    if result.get("current_xi_certified") or result.get("expected_lineups"):
        raise RuntimeError("This static historical-bridge build must not certify a current XI")
    if len(result.get("players",[]))<250:
        raise RuntimeError("Insufficient role-linked players")
    target=ROOT/"app"/"role-data.js"
    target.write_text("window.FPL_ROLE_DATA="+json.dumps(result,ensure_ascii=False,separators=(",",":"),allow_nan=False)+";\n",encoding="utf-8")
    print("Frozen role priors built:",len(result["players"]),"players;",result.get("historical_tactical_lineups_found",0),"historical team games. Current XI not certified.")

if __name__=="__main__":main()
