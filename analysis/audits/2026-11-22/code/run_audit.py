"""Offline audit reproduction: scores archived draws; does not run model simulations."""
from pathlib import Path
import subprocess,sys
from verify_inputs import ROOT,verify
import json
verify(ROOT,json.loads((ROOT/'input-integrity.json').read_text()))
for script in ['evaluate_archived_forecasts.py','build_error_atlas.py','compare_official_ep_next.py','verify_scoring_rules.py']:
 print('Running',script,flush=True);subprocess.run([sys.executable,str(Path(__file__).with_name(script))],check=True,stdout=subprocess.DEVNULL)
print('Audit complete. No fit, simulation, publication or network requests executed.')
