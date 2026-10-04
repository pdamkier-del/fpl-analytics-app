"""Compare immutable control rosters with recovered predeadline FPL listing.

An absent player is unknown at this snapshot, not proof of ineligibility.
FPL listing is distinct from a complete football matchday roster.
"""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from fpl_v1_1_model.paired_joint import read_frozen_table

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,default=ROOT/'analysis/results/joint-deadline-roster-audit-v1')
    a=ap.parse_args()
    if a.out.exists():
        raise FileExistsError('Use a new immutable audit directory')
    state_path=ROOT/'analysis/results/joint-deadline-snapshots-v1'
    state=read_frozen_table(state_path,'states')
    bpath=ROOT/'analysis/results/v2-reproduced/pstart_v2_fixture_holdout_2025_26.csv'
    b=pd.read_csv(bpath);b=b[b.gw>=22].copy()
    if state[['gw','player_uuid']].duplicated().any() or state.player_uuid.isna().any():
        raise ValueError('Unique complete stable state identities required')
    x=b.merge(state,on=['gw','player_uuid'],how='left',validate='many_to_one',suffixes=('','_snapshot'))
    x['snapshot_evidence']='matching_team_position'
    x.loc[x.fpl_element_id.isna(),'snapshot_evidence']='not_observed_in_selected_snapshot'
    x.loc[x.fpl_element_id.notna() & (x.team_id!=x.team_id_snapshot),'snapshot_evidence']='team_disagreement'
    x.loc[x.fpl_element_id.notna() & (x.pos!=x.position),'snapshot_evidence']='position_disagreement'
    missing=read_frozen_table(ROOT/'analysis/results/joint-paired-inputs-v1','missing_components')
    columns=['fixture_uuid','player_uuid','gw','team_id','pos','snapshot_evidence','fpl_element_id',
             'web_name','cutoff','observed_at','price_tenths','status_code','source_blob_sha']
    absent=x[x.snapshot_evidence!='matching_team_position'][columns]
    gaps=missing.merge(x[columns],on=['fixture_uuid','player_uuid','gw','team_id','pos'],validate='one_to_one')
    a.out.mkdir(parents=True)
    outputs=[]
    for name,frame in [('missing_component_evidence',gaps),('unverified_roster_rows',absent)]:
        path=a.out/(name+'.csv');frame.to_csv(path,index=False,lineterminator='\n')
        outputs.append(dict(path=path.name,rows=len(frame),sha256=digest(path)))
    ages=[s['snapshot_age_hours'] for s in json.loads((state_path/'manifest.json').read_text())['sources']]
    result=dict(parent_checkpoint='7ac64e366d0790449ec12849f4a9e524b7351789',season='2025-26',
        classification='reused_diagnostic_input_audit',control_rows=len(x),
        roster_evidence_counts=x.snapshot_evidence.value_counts().to_dict(),
        missing_component_rows=len(gaps),missing_evidence_counts=gaps.snapshot_evidence.value_counts().to_dict(),
        max_snapshot_age_hours=max(ages),min_snapshot_age_hours=min(ages),
        full_roster_replay_ready=False,outputs=outputs,
        sources=[dict(path=str(p.relative_to(ROOT)),sha256=digest(p)) for p in
            [state_path/'manifest.json',bpath,ROOT/'analysis/results/joint-paired-inputs-v1/manifest.json',Path(__file__)]],
        interpretation=[
            '15 first-entry component rows have verified predeadline FPL listing/team/position evidence.',
            '31 first-entry rows are not observed in the selected snapshots; absence does not prove that they were not added later before deadline.',
            'There is one additional unverified roster row outside the missing-component inventory.',
            'FPL listing is not a complete physical football roster, nor evidence that a player is fit or will appear.',
            'Do not remove unverified players from event allocation or fill their missing components with zero.'],
        next_required=[
            'Resolve predeadline roster/position evidence for the 31 first entrants and the additional row, or explicitly limit a new controlled replay population.',
            'Version and test a first-entry component path using frozen parameters and predeadline sufficient statistics.',
            'Audit original component forecast timing before promoting archived fixture forecasts to deadline replay inputs.'],
        unchanged='Original adapter/simulator, transfer/chip policy, Core database and old diagnostic/input files')
    (a.out/'manifest.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:result[k] for k in ['roster_evidence_counts','missing_evidence_counts','max_snapshot_age_hours','full_roster_replay_ready']},indent=2))


if __name__=='__main__':
    main()
