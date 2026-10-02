"""Audit recovered historical starter roles; write derived CAM data without raw edits.

This does not infer new geometry or claim historical forecast validation.
"""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--roles', required=True)
ap.add_argument('--out', required=True)
args = ap.parse_args()
source = Path(args.roles)
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
d = pd.read_csv(source)
assert not d.duplicated(['fixture_uuid','team_id','player_uuid']).any()
assert d.groupby(['fixture_uuid','team_id']).size().eq(11).all()
original = d.copy()
d['role'] = d.role.replace({'AM':'CAM'})
d.to_csv(out/'starter_roles_cam.csv',index=False)
original.loc[original.role.eq('AM')].assign(corrected_role='CAM').to_csv(out/'cam_changes.csv',index=False)
for key in ('gw','team_id','player_uuid','formation'):
    summary = d.groupby(key).agg(starters=('role','size'), cam_starts=('role',lambda x:x.eq('CAM').sum()))
    summary.to_csv(out/f'coverage_by_{key}.csv')
metrics = {
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'classification_source': 'recovered starter slot-role artifact; no average-position coordinates supplied',
    'starter_rows':len(d),'teams':int(d.team_id.nunique()),'gameweeks':int(d.gw.nunique()),
    'fixtures':int(d.fixture_uuid.nunique()),'players':int(d.player_uuid.nunique()),
    'missing_roles':int(d.role.isna().sum()),'missing_formation':int(d.formation.isna().sum()),
    'cam_starts':int(d.role.eq('CAM').sum()),
    'cam_players':int(d.loc[d.role.eq('CAM'),'player_uuid'].nunique()),
    'cam_teams':int(d.loc[d.role.eq('CAM'),'team_id'].nunique()),
    'role_counts':{str(k):int(v) for k,v in d.role.value_counts().items()},
    'changed_from':{'AM':int(original.role.eq('AM').sum())},
    'geometry_reclassification': 'not performed; raw average-position and lineup inputs are still missing',
    'bench_and_sub_coverage': 'not present in this starter-only artifact',
}
(out/'coverage.json').write_text(json.dumps(metrics,indent=2)+'\n')
print(json.dumps(metrics,indent=2))
