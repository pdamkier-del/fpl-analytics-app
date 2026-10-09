#!/usr/bin/env python3
"""Publisher bundle regression: all new forecast/model assets ship via one click."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import datetime, timezone
import importlib.util, io, json, hashlib, sys, zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("release_script",ROOT/"scripts/publish_fpl_update.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def main():
    with TemporaryDirectory() as temp:
        out=Path(temp)
        with patch.object(module,"UPDATES",out),patch.object(sys,"argv",["publish_fpl_update.py",
                "--app-version","99.99-test","--message","CI package validation"]),\
             patch.object(module.subprocess,"run",return_value=None):
            module.main()
        manifest=json.loads((out/"manifest.json").read_text(encoding="utf8"))
        archive=out/"app-99.99-test.zip"
        data=archive.read_bytes()
        assert hashlib.sha256(data).hexdigest()==manifest["app"]["sha256"]
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            items=set(z.namelist())
            required={
              "start_app.py","model/forecast_preview.py","model/decision_optimizer.py",
              "config/fpl_locked_model.json","src/fpl_xpts/final_chip_coordinator.py",
              "src/fpl_xpts/bench_boost_policy.py","src/fpl_xpts/chip_planner.py",
              "src/fpl_v1_1_model/joint_simulator.py",
              "app/forecast-center.html","app/models.html","app/model-tree-data.js",
              "app/model-tree-ui.js","app/nav.js"
            }
            assert not required-items, sorted(required-items)
            assert b"/api/forecast/preview" in z.read("app/forecast-center.html")
            assert b"forecast_preview.forecast_preview" in z.read("start_app.py")
            club=z.read("app/index.html")
            assert b"MM-rolledata mangler" in club
            assert b"const roles=[\'GK\',\'RB\'" not in club
            assert b"roleSet=new Set" in club
        print("PUBLISHER_BUNDLE_OK",len(items),"files",len(data),"bytes",flush=True)

if __name__=="__main__": main()
