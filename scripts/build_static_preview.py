"""Publish a clearly labelled static bridge preview for the free GitHub Pages app.

This does not run the locked MM/PM/TS model or import live injury data.
The generated_at timestamp only describes publication, never forecast freshness.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"model"))
from forecast_preview import forecast_preview

def main():
    data=json.loads((ROOT/"model"/"base_data.json").read_text(encoding="utf-8"))
    default=[496,572,8,173,204,229,469,15,40,154,290,399,165,346,411]
    latest=ROOT/"data_v1_1"/"derived"/"fpl_schedule_knowledge"/"live"/"latest.json"
    official=json.loads(latest.read_text(encoding="utf-8")) if latest.is_file() else {}
    result=forecast_preview(data,{"player_ids":default},official=official)
    result["publication"]={"generated_at":datetime.now(timezone.utc).isoformat(),"mode":"static_bridge_preview","locked_forecast_run":False,"note":"Not a fresh locked MM/PM/TS prediction. Publication timestamp does not indicate data freshness."}
    target=ROOT/"app"/"forecast-snapshot.json"
    target.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":"),allow_nan=False),encoding="utf-8")
    print("Wrote static bridge snapshot",target.stat().st_size)

if __name__=="__main__": main()
