"""Publish a *verified* locked final-model artifact or an explicit blocked state.

This adapter does not refit or substitute the locked MM/PM/TS/chips. The
model's original historical runners must be ported to an as-of live feature
pipeline before a valid manifest can be provided. Fail closed otherwise.
"""
from __future__ import annotations
import hashlib,json,os
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"app"
CONFIG=ROOT/"config"/"fpl_locked_model.json"
INPUT=ROOT/"work"/"live-final-model"/"manifest.json"
OUTPUT=APP/"final-forecast.json"
LOCKED_PARTS=("mm","pm_vfinal","ts_v3","chips")

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def iso(value):
    return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(timezone.utc)

def construct():
    official=json.loads((APP/"current-players.json").read_text(encoding="utf-8"))
    cfg=json.loads(CONFIG.read_text(encoding="utf-8"))
    observed=iso(official["fetched_at"])
    result={"schema_version":1,"model_version":cfg["version"],
        "locked_model_active":False,"status":"blocked_missing_verified_live_chain",
        "data_asof":official["fetched_at"],"next_gw":official.get("next_gw"),
        "current_players":len(official["players"]),
        "parts":{k:"not_verified_live" for k in LOCKED_PARTS},
        "parameters":{"ts_horizon_gw":cfg["transfer_strategy"]["horizon_gw"],
            "rho":cfg["transfer_strategy"]["rho"],
            "ts_weights":cfg["transfer_strategy"]["weights"],
            "hit_uncertainty_buffer":cfg["transfer_strategy"]["hit_uncertainty_buffer"]},
        "players":[],"recommendations":[],
        "blockers":["No current-season cutoff-safe frozen MM inference artifact",
          "No vFinal simulation from that MM artifact",
          "No TS v3 run on the same verified PM outputs",
          "No locked FH/WC/BB/TC plan on the same verified state"]}
    if not INPUT.exists():return result
    m=json.loads(INPUT.read_text(encoding="utf-8"))
    if m.get("model_version")!=cfg["version"]:raise RuntimeError("Live final artifact model version differs from locked config")
    if m.get("data_asof")!=official["fetched_at"]:raise RuntimeError("Live final artifact differs from official source timestamp")
    if m.get("next_gw")!=official.get("next_gw"):raise RuntimeError("Live final artifact GW mismatch")
    if not 0 <= (datetime.now(timezone.utc)-observed).total_seconds()<72*3600:raise RuntimeError("Official data stale")
    parts=m.get("components") or {}
    for part in LOCKED_PARTS:
        row=parts.get(part) or {}
        file=ROOT/str(row.get("path",""))
        if not row.get("locked") or not file.is_file() or not file.is_relative_to(ROOT):
            raise RuntimeError("Unverified component: "+part)
        if digest(file)!=row.get("sha256"):raise RuntimeError("Artifact digest mismatch: "+part)
        if row.get("data_asof")!=official["fetched_at"]:raise RuntimeError("Component timestamp mismatch: "+part)
        result["parts"][part]="verified"
    pred=ROOT/str(m.get("forecast_path",""))
    if not pred.is_file() or not pred.is_relative_to(ROOT):raise RuntimeError("Missing final forecast")
    if digest(pred)!=m.get("forecast_sha256"):raise RuntimeError("Forecast integrity failure")
    rows=json.loads(pred.read_text(encoding="utf-8"))
    if not isinstance(rows,list) or len(rows)<250:raise RuntimeError("Incomplete player forecast")
    valid_ids={p["id"] for p in official["players"]}
    for row in rows:
        if row.get("id") not in valid_ids:raise RuntimeError("Player not in current FPL season")
        if not isinstance(row.get("weeks"),list) or not row["weeks"]:raise RuntimeError("Missing forecast weeks")
        for w in row["weeks"]:
            if not isinstance(w.get("xpts"),(int,float)) or not 0<=w["xpts"]<=50:raise RuntimeError("Invalid xP")
    result.update(status="verified_locked_live",locked_model_active=True,players=rows,
                  recommendations=m.get("recommendations") or [],blockers=[],
                  verified_at=datetime.now(timezone.utc).isoformat())
    return result

def main():
    result=construct()
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":"),allow_nan=False),encoding="utf-8")
    print("FINAL MODEL CONTRACT:",result["status"],"GW",result["next_gw"],
          "source players",result["current_players"],
          "verified modules",sum(x=="verified" for x in result["parts"].values()))
if __name__=="__main__":main()
