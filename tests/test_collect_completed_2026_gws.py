import importlib.util
from pathlib import Path
import json

spec=importlib.util.spec_from_file_location("ingest",Path(__file__).resolve().parents[1]/"scripts/collect_completed_2026_gws.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def payload(endpoint):
    if endpoint=="/bootstrap-static/":
        return {"events":[{"id":1,"finished":True,"data_checked":True,
                            "deadline_time":"2026-08-14T17:00:00Z"}]}
    if endpoint=="/fixtures/":
        return [{"id":1001,"event":1,"finished":True}]
    if endpoint=="/event/1/live/":
        return {"elements":{"42":{"stats":{"minutes":90,"total_points":6},
                                   "explain":[{"fixture":1001,"stats":[]}]},
                            "43":{"stats":{"minutes":0},"explain":[]}}}
    raise AssertionError(endpoint)

def test_keyed_official_live_elements_are_normalized(monkeypatch,tmp_path):
    monkeypatch.setattr(mod,"get_json",lambda session,endpoint:payload(endpoint))
    result=mod.collect(tmp_path)
    assert result["completed_gws"][0]["player_rows"]==2
    saved=json.loads((tmp_path/"gw01.json").read_text())
    assert [r["id"] for r in saved["official_player_live"]]==[42,43]
    assert saved["observed_at_utc"]

def test_rerun_preserves_original_observation_time(monkeypatch,tmp_path):
    monkeypatch.setattr(mod,"get_json",lambda session,endpoint:payload(endpoint))
    mod.collect(tmp_path)
    before=(tmp_path/"gw01.json").read_bytes()
    mod.collect(tmp_path)
    assert (tmp_path/"gw01.json").read_bytes()==before

def test_conflicting_provider_player_identity_is_rejected(monkeypatch,tmp_path):
    def broken(session,endpoint):
        p=payload(endpoint)
        if endpoint=="/event/1/live/":
            p["elements"]["42"]["id"]=123
        return p
    monkeypatch.setattr(mod,"get_json",broken)
    try:mod.collect(tmp_path)
    except ValueError as exc:assert "conflicting player ID" in str(exc)
    else:raise AssertionError("Conflicting player identity accepted")
