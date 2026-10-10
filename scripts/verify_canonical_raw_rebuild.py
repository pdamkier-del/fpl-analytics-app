#!/usr/bin/env python3
"""Rebuild all numerical adapters twice; assert exact inputs and outputs.

No recorded predictions replace a rebuilt field. Source checkpoint, cutoff,
parameters and simulator seeds remain fixed throughout both runs.
"""
import json, subprocess, sys, hashlib
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from audit_live_raw_reproduction import numeric_diff
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
WORK=ROOT/'work/live-final-model'
STEPS=['build_locked_live_sequence_features','build_locked_live_performance_features',
       'build_locked_live_v2_baseline','build_live_mm_training_features','run_locked_live_mm_inference',
       'build_live_pm_observed_team_xg','run_live_vfinal_team_latent','run_live_vfinal_keeper_saves',
       'run_live_vfinal_player_components','join_live_vfinal_inputs','restore_frozen_live_assist_prior',
       'build_live_penalty_fpl_team_ids','build_verified_live_penalty_bps','restore_original_bps_bounds',
       'build_live_vfinal_full_event_components']
WATCH=[BASE/'reconstructed_training_features.csv.gz',WORK/'mm_frozen_diagnostic_six_gw.csv.gz',
       BASE/'future_team_goal_lambdas.csv.gz',BASE/'vfinal_live_full_simulator_input.csv.gz',BASE/'live_vfinal_fixture_xp.csv.gz']
def execute(name,args=()):
    subprocess.run([sys.executable,str(ROOT/'scripts/locked_numerical_runtime.py'),str(ROOT/'scripts'/f'{name}.py'),*map(str,args)],cwd=ROOT,check=True)
def rebuild():
    for name in STEPS:execute(name)
    origin=int(json.loads((WORK/'source_manifest.json').read_text())['target_gw'])
    execute('run_live_vfinal_penalty_state',['--origin',origin,'--roster',BASE/'vfinal_live_full_event_inputs.csv.gz',
        '--attempts',BASE/'verified_penalty_attempts.csv.gz','--sides',BASE/'verified_penalty_team_sides.csv.gz','--teams',BASE/'verified_penalty_team_ids.csv.gz'])
    execute('run_live_vfinal_bps',['--target',BASE/'vfinal_live_full_event_inputs.csv.gz','--ledger',BASE/'verified_bps_action_ledger.csv.gz'])
    execute('assemble_live_vfinal_inputs',['--base',BASE/'vfinal_live_full_event_inputs.csv.gz'])
    execute('run_live_vfinal_joint_simulation',['--input',BASE/'vfinal_live_full_simulator_input.csv.gz'])
def main():
    rebuild();first={p:pd.read_csv(p,low_memory=False) for p in WATCH}
    rebuild();report={'classification':'CANONICAL_RUNTIME_TWO_RAW_REBUILDS','locked_model_active':False,
        'cutoff':str(first[BASE/'vfinal_live_full_simulator_input.csv.gz'].cutoff.iloc[0]),
        'source_capture':json.loads((WORK/'source_manifest.json').read_text())['observed_at'],'comparisons':{}}
    for path,a in first.items():
        b=pd.read_csv(path,low_memory=False);delta=numeric_diff(a,b)
        equal=a.equals(b);report['comparisons'][path.name]={'exact_equal':equal,'numeric_differences':delta,
            'second_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rows':len(b)}
    report['passed']=all(x['exact_equal'] for x in report['comparisons'].values())
    out=WORK/'canonical_raw_rebuild.json';out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
    if not report['passed']:raise SystemExit('Raw rebuild remains non-reproducible; release blocked')
if __name__=='__main__':main()
