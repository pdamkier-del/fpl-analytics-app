import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location("adapter",Path(__file__).resolve().parents[1]/"scripts/bridge_official_gw_to_replay.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def fixture():
    return {"gw":1,"official_event":{"finished":True,"data_checked":True,"deadline_time":"2026-08-14T17:30:00Z"},
       "official_fixtures":[{"id":111,"finished":True}],
       "official_player_live":[{"id":42,"explain":[{"fixture":111,
          "stats":[{"identifier":"minutes","value":90},{"identifier":"total_points","value":6}]}]}]}

def test_preserves_fixture_stats_without_fabricating_start():
    result=mod.rows_for_gameweek(fixture(),None)
    assert len(result)==1
    assert result[0]["fixture_id"]==111
    assert result[0]["minutes"]==90
    assert result[0]["started"] is None

def test_rejects_bad_fixture():
    p=fixture()
    p["official_player_live"][0]["explain"][0]["fixture"]=999
    try: mod.rows_for_gameweek(p,None)
    except ValueError: pass
    else: raise AssertionError("Unknown fixture accepted")

def test_rejects_missing_explain():
    p=fixture()
    del p["official_player_live"][0]["explain"]
    try: mod.rows_for_gameweek(p,None)
    except ValueError: pass
    else: raise AssertionError("Missing per-fixture provenance accepted")
