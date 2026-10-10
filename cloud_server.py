"""Minimal authenticated shared FPL web backend for mobile and desktop.

No forecast engine parameters are changed. Preview data is explicitly labelled
as a bridge preview. Run behind HTTPS; configure FPL_APP_USER/FPL_APP_PASSWORD
and mount durable FPL_DATA_DIR. Do not expose the legacy mutating model APIs.
"""
from __future__ import annotations
import base64
import hmac
import json
import os
from pathlib import Path
import sqlite3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import sys

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"
sys.path.insert(0, str(ROOT / "model"))
import forecast_preview
import decision_optimizer

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
STORE = Path(os.getenv("FPL_DATA_DIR", "/data")).resolve()
USER = os.getenv("FPL_APP_USER", "")
PASSWORD = os.getenv("FPL_APP_PASSWORD", "")
DEFAULT_IDS = [496,572,8,173,204,229,469,15,40,154,290,399,165,346,411]

def initialize():
    if not USER or not PASSWORD or len(PASSWORD) < 20:
        raise RuntimeError("Set FPL_APP_USER and FPL_APP_PASSWORD (at least 20 characters)")
    STORE.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(STORE / "users.sqlite3") as db:
        db.execute("CREATE TABLE IF NOT EXISTS squad (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)")

def read_squad():
    with sqlite3.connect(STORE / "users.sqlite3", timeout=10) as db:
        row = db.execute("SELECT body FROM squad WHERE id=1").fetchone()
    return json.loads(row[0]) if row else {"player_ids": DEFAULT_IDS}

def write_squad(squad):
    with sqlite3.connect(STORE / "users.sqlite3", timeout=10) as db:
        db.execute("INSERT INTO squad(id,body) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                   (json.dumps(squad, ensure_ascii=False),))
    return squad

def data():
    return json.loads((ROOT/"model"/"base_data.json").read_text(encoding="utf-8"))

def official():
    p=ROOT/"data_v1_1"/"derived"/"fpl_schedule_knowledge"/"live"/"latest.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

def validate_squad(payload):
    if not isinstance(payload, dict):
        raise ValueError("Squad must be an object")
    raw=payload.get("player_ids")
    if not isinstance(raw, list) or len(raw)!=15 or any(type(x)!=int for x in raw):
        raise ValueError("Squad requires exactly 15 numeric player IDs")
    if len(set(raw))!=15:
        raise ValueError("Squad contains duplicates")
    allowed = {int(p["id"]) for p in data().get("forecasts", [])}
    if not set(raw) <= allowed:
        raise ValueError("Unknown player ID")
    out={k:v for k,v in payload.items() if k in {"player_ids","captain_id","vice_captain_id","bench_order","bank","free_transfers","team_name"}}
    if "bench_order" in out:
        b=out["bench_order"]
        if not isinstance(b,list) or len(b)!=4 or any(type(x)!=int for x in b) or len(set(b))!=4 or not set(b)<=set(raw):
            raise ValueError("Invalid bench")
    for k in ("captain_id","vice_captain_id"):
        if out.get(k) is not None and (type(out[k])!=int or out[k] not in raw):
            raise ValueError("Invalid captain")
    if out.get("bank") is not None:
        b=out["bank"]
        if type(b) not in (int,float) or not 0<=b<=100: raise ValueError("Invalid bank")
    if out.get("free_transfers") is not None:
        f=out["free_transfers"]
        if type(f)!=int or not 0<=f<=5: raise ValueError("Invalid free transfers")
    return out

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP), **kwargs)
    def authorized(self):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "): return False
        try:
            value = base64.b64decode(header[6:], validate=True).decode("utf-8")
        except (ValueError, UnicodeError):
            return False
        expected = f"{USER}:{PASSWORD}"
        return hmac.compare_digest(value.encode(), expected.encode())
    def guard(self):
        if self.authorized(): return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="FPL Analytics"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        return False
    def json(self, value, status=200):
        body=json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        if not self.guard(): return
        path=urlsplit(self.path).path
        if path=="/api/health": return self.json({"ok":True,"mode":"cloud_preview_only"})
        if path=="/api/user/squad": return self.json(read_squad())
        if path=="/api/forecast/preview":
            return self.json(forecast_preview.forecast_preview(data(),read_squad(),official=official()))
        if path=="/api/update/status":
            return self.json({"ok":True,"mode":"bridge_preview_only","note":"No live locked model run"})
        if path=="/api/model/config":
            p=ROOT/"model"/"active.json"
            return self.json(json.loads(p.read_text(encoding="utf-8")))
        if path=="/api/model/status":
            d=data()
            return self.json({"engine_mode":"bridge_preview_only","source_model_version":d.get("meta",{}).get("model_version"),"forecast_players":len(d.get("forecasts",[]))})
        if path.startswith("/api/"):
            return self.json({"error":"Not implemented in cloud preview"},501)
        if path=="/": self.path="/mobile.html"
        return super().do_GET()
    def do_POST(self):
        if not self.guard(): return
        path=urlsplit(self.path).path
        n=int(self.headers.get("Content-Length","0"))
        if n>32768: return self.json({"error":"Payload too large"},413)
        try:
            payload=json.loads(self.rfile.read(n) or b"{}")
            if path=="/api/user/squad":
                return self.json(write_squad(validate_squad(payload)))
            if path in ("/api/optimizer/plan","/api/optimizer/manual"):
                if not isinstance(payload,dict): raise ValueError("Invalid payload")
                if path.endswith("/plan"): result=decision_optimizer.optimize_plan(data(),read_squad(),payload)
                else: result=decision_optimizer.manual_transfer(data(),read_squad(),payload)
                return self.json(result)
            if path=="/api/forecast/refresh":
                return self.json({"ok":False,"error":"Live locked MM/PM/TS forecast pipeline has not been certified or deployed. Existing preview was not refreshed."},503)
            return self.json({"error":"Not implemented"},501)
        except (ValueError,KeyError,TypeError) as ex:
            return self.json({"error":str(ex)},400)

if __name__=="__main__":
    initialize()
    print(f"FPL cloud preview listening on {HOST}:{PORT}")
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
