#!/usr/bin/env python3
"""Replay immutable simulator inputs; verify every point/minute component."""
import hashlib,json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_live_vfinal_joint_simulation import simulate

def main():
    base=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
    source=base/'vfinal_live_full_simulator_input.csv.gz'
    original=pd.read_csv(base/'live_vfinal_fixture_xp.csv.gz')
    replay,audit=simulate(pd.read_csv(source,low_memory=False))
    keys=['fixture_uuid','player_uuid']
    original=original.sort_values(keys).reset_index(drop=True);replay=replay.sort_values(keys).reset_index(drop=True)
    if not original[keys].equals(replay[keys]):raise ValueError('Checkpoint identity replay differs')
    cols=original.select_dtypes('number').columns
    dif=(original[cols]-replay[cols]).abs().max()
    report={'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'fixtures':audit['fixtures'],'rows':len(replay),
            'max_absolute_difference_by_field':dif.to_dict(),'replay_matches':bool(dif.le(1e-12).all()),'locked_model_active':False}
    out=ROOT/'work/live-final-model/immutable_input_replay_audit.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    if not report['replay_matches']:raise ValueError('Immutable input simulator replay failed')
if __name__=='__main__':main()
