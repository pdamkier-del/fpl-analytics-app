"""Verify recovered sources and packed paired inputs/results without refitting."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import subprocess

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
    recovered=ROOT/'analysis/results/joint-component-recovery-v1/manifest.json'
    for entry in json.loads(recovered.read_text())['files']:
        checks+=1
        if digest(ROOT/entry['path'])!=entry['sha256']:errors.append(entry['path']+': recovered component bytes differ')
    audit_path=ROOT/'analysis/results/joint-cold-start-audit-v1'
    audit=json.loads((audit_path/'manifest.json').read_text())
    for entry in audit['sources']:
        checks+=1
        if digest(ROOT/entry['path'])!=entry['sha256']:errors.append(entry['path']+': audit source changed')
    checks+=1
    if digest(audit_path/audit['output']['path'])!=audit['output']['sha256']:
        errors.append('Cold-start audit rows changed')
    checks+=1
    if audit['missing_rows']!=inputs['missing_component_rows'] or audit['affected_fixtures']!=inputs['blocked_fixtures']:
        errors.append('Cold-start audit does not cover the frozen missing cohort')
    latest={}
    for name in ['joint-deadline-roster-audit-v1','joint-component-timing-audit-v1']:
        path=ROOT/'analysis/results'/name
        latest[name]=json.loads((path/'manifest.json').read_text())
        for entry in latest[name]['sources']:
            checks+=1
            if digest(ROOT/entry['path'])!=entry['sha256']:errors.append(entry['path']+': latest audit source changed')
        for entry in latest[name]['outputs']:
            checks+=1
            if digest(path/entry['path'])!=entry['sha256']:errors.append(name+': audit output changed')
        for entry in latest[name].get('original_experiment_sources',[]):
            checks+=1
            if digest(path/entry['preserved_source'])!=entry['member_sha256']:errors.append(name+': original experiment changed')
    deadline_report=ROOT/'work/joint-deadline-integrity-current.json'
    try:
        subprocess.run([sys.executable,str(ROOT/'scripts/check_joint_deadline_snapshots.py'),
                        '--report',str(deadline_report)],check=True,capture_output=True,text=True)
        checks+=json.loads(deadline_report.read_text())['checks']
    except subprocess.CalledProcessError as e:
        errors.append('Deadline source integrity failed: '+e.stderr[-1000:])
    roster=latest['joint-deadline-roster-audit-v1']
    timing=latest['joint-component-timing-audit-v1']
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
                    affected_fixtures=inputs['blocked_fixtures'],
                    core_no_asof_registration=audit['no_asof_registration'],
                    core_no_asof_player_state=audit['no_asof_player_state'],
                    verified_external_first_entry_rows=roster['missing_evidence_counts'].get('matching_team_position',0),
                    first_entry_rows_not_observed_in_selected_snapshot=roster['missing_evidence_counts'].get('not_observed_in_selected_snapshot',0),
                    total_unverified_roster_rows=roster['roster_evidence_counts'].get('not_observed_in_selected_snapshot',0),
                    original_parameters_available=audit['original_parameters_available'],
                    required='Resolve remaining roster evidence and freeze a deadline-batched first-entry component contract; original parameters and 17 predeadline snapshots recovered'),
                component_timing=dict(deadline_component_inputs_ready=False,
                    fixture_contexts_with_postdeadline_league_state=timing['fixtures_with_postdeadline_league_state'],
                    player_rows_with_postdeadline_history=timing['player_rows_with_postdeadline_player_history'],
                    interpretation='Structural exposure in original sequential ordering; no numerical impact estimate'),
                remaining=['Full first-deadline horizon forecasts/eligibility/price/schedule inputs',
                           '2025/26 scoring mode and unresolved BPS subtypes/background; audit recorded separately',
                           'Season orchestration including GW16 AFCON transfer top-up',
                           'Complete cutoff-safe cup and active-competition state; independent test period'])
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2));raise SystemExit(bool(errors))


if __name__=='__main__':main()
