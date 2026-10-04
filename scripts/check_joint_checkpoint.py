"""Verify recovered sources and packed paired inputs/results without refitting."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.paired_joint import read_frozen_table


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report',type=Path,default=ROOT/'work/joint-readiness-20261004.json')
    a=ap.parse_args();errors=[];checks=0
    for name in ['joint-source-recovery-20261004.json','replay-source-recovery-20261004.json']:
        m=json.loads((ROOT/'docs/checkpoints'/name).read_text())
        for entry in m['files']:
            checks+=1
            if digest(ROOT/entry['path'])!=entry['sha256']:errors.append(entry['path']+': recovered bytes differ')
    im=ROOT/'analysis/results/joint-paired-inputs-v1/manifest.json'
    inputs=json.loads(im.read_text())
    for entry in inputs['tracked_inputs']:
        checks+=1
        if digest(ROOT/entry['path'])!=entry['sha256']:errors.append(entry['path']+': input changed')
    if digest(ROOT/'scripts/freeze_joint_diagnostic_inputs.py')!=inputs['code_sha256']:
        errors.append('Frozen-input builder changed')
    for folder in ['joint-paired-inputs-v1','joint-paired-diagnostic-v1']:
        path=ROOT/'analysis/results'/folder
        m=json.loads((path/'manifest.json').read_text())
        for entry in m['outputs']:
            try:read_frozen_table(path,entry['name']);checks+=len(entry['parts'])+2
            except Exception as e:errors.append(folder+': '+str(e))
        for entry in m.get('code',[]):
            checks+=1
            if digest(ROOT/entry['path'])!=entry['sha256']:errors.append(entry['path']+': code changed')
        if m.get('inputs_manifest_sha256') and digest(im)!=m['inputs_manifest_sha256']:
            errors.append('Diagnostic frozen-input manifest changed')
    report=dict(integrity_passed=not errors,checks=checks,errors=errors,
                simulator_imports_available=True,paired_diagnostic_completed=True,
                full_roster_replay_ready=False,full_season_replay_ready=False,
                concrete_data_gap=dict(missing_frozen_component_rows=inputs['missing_component_rows'],
                    affected_fixtures=inputs['blocked_fixtures'],required='Frozen attack/assist/discipline forecasts for 46 newly entering player-fixture rows; DC also missing for the 40 non-GK rows'),
                remaining=['Full first-deadline horizon forecasts/eligibility/price/schedule inputs',
                           '2025/26 scoring mode and unresolved BPS subtypes/background; audit recorded separately',
                           'Season orchestration including GW16 AFCON transfer top-up',
                           'Complete cutoff-safe cup and active-competition state; independent test period'])
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2));raise SystemExit(bool(errors))


if __name__=='__main__':main()
