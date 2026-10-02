"""Check that isolated AM -> CAM renaming preserves historical q/H numerically."""
import argparse
import json
from pathlib import Path
import pandas as pd

ap=argparse.ArgumentParser()
ap.add_argument('--legacy',required=True)
ap.add_argument('--cam',required=True)
ap.add_argument('--out',required=True)
a=ap.parse_args();report={}
for name,keys in [('player_role_state',['asof','source_match_id','team_external_id','external_player_id','role']),
                  ('role_capacities',['asof','source_match_id','team_external_id','role']),
                  ('role_candidates',['asof','source_match_id','team_external_id','external_player_id','role'])]:
    frames=[]
    for directory in [a.legacy,a.cam]:
        p=Path(directory)/(name+'.csv')
        frames.append(pd.read_csv(p if p.exists() else Path(str(p)+'.gz')))
    old,new=frames
    for col in ['role','primary_role']:
        if col in old: old[col]=old[col].replace({'AM':'CAM'})
    old=old.sort_values(keys).reset_index(drop=True)
    new=new.sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(old,new,check_exact=False,rtol=1e-12,atol=1e-12)
    report[name]={'rows':len(new),'canonical_cam_equivalence':'PASS'}
report['scope']='historical feature equivalence on all recovered geometry-imported games; not forecast/OOS performance'
report['prediction_effect']='CAM replaces central AM without changing model dimensions; role-name-invariant transport is tested separately'
Path(a.out).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
