#!/usr/bin/env python3
"""Offline official FPL bootstrap/fixture snapshot test, no network."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import importlib.util,json

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("snapshot",ROOT/"scripts/snapshot_fpl_schedule.py")
snapshot=importlib.util.module_from_spec(spec);spec.loader.exec_module(snapshot)

def test():
    with TemporaryDirectory() as temp:
        out=Path(temp);snaps=out/"snapshots"
        teams=[{"id":1,"name":"Home"},{"id":2,"name":"Away"}]
        fixtures=[{"id":1001,"event":8,"team_h":1,"team_a":2,"kickoff_time":"2026-10-10T15:00:00Z",
                   "started":False,"finished":False}]
        boot={"teams":teams,"events":[{"id":7,"finished":True,"is_next":False},
                                         {"id":8,"finished":False,"is_next":True}],
              "elements":[{"id":101,"web_name":"Example","status":"d","chance_of_playing_next_round":50,
                           "news":"Uncertain","now_cost":70,"team":1,"element_type":3}]}
        def fake_fetch(url):
            return fixtures if "/fixtures/" in url else boot
        with patch.object(snapshot,"OUT",out),patch.object(snapshot,"SNAPSHOTS",snaps),\
             patch.object(snapshot,"fetch_json",side_effect=fake_fetch):
            snapshot.main()
        doc=json.loads((out/"latest.json").read_text(encoding="utf8"))
        assert doc["schema_version"]==2
        assert doc["official_next_gw"]==8
        assert doc["players"][0]["chance_next_round"]==50
        assert doc["players"][0]["price_tenths"]==70
        assert doc["event_status"][7]["event"]==8
        assert len(doc["fixtures"])==1
        assert doc["observed_at_utc"]
        print("OFFICIAL_SCHEDULE_SNAPSHOT_OK",doc["official_next_gw"])
if __name__=="__main__":test()
