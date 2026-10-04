"""Verify the frozen deadline player-component experiment and explicit gaps."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from fpl_v1_1_model.paired_joint import read_frozen_table

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report',type=Path,default=ROOT/'work/deadline-player-integrity.json')
    a=ap.parse_args();folder=ROOT/'analysis/results/deadline-player-components-v1'
    m=json.loads((folder/'manifest.json').read_text());checks=0
    for s in m['sources']:
        if hashlib.sha256((ROOT/s['path']).read_bytes()).hexdigest()!=s['sha256']:
            raise ValueError('Frozen component source changed: '+s['path'])
        checks+=1
    tables={x['name']:read_frozen_table(folder,x['name']) for x in m['outputs']}
    checks+=sum(len(x['parts'])+2 for x in m['outputs'])
    f=tables['components'];blocked=tables['blocked_roster'];history=tables['history_summary']
    keys=['fixture_uuid','player_uuid']
    if f[keys].duplicated().any() or blocked[keys].duplicated().any():
        raise ValueError('Duplicate roster rows')
    b=pd.read_csv(ROOT/'analysis/results/v2-reproduced/pstart_v2_fixture_holdout_2025_26.csv',usecols=keys+['gw'])
    b=b[b.gw>=22]
    union=pd.concat([f[keys],blocked[keys]])
    if union.duplicated().any() or len(union)!=len(b) or not union.merge(b[keys],on=keys,how='outer',indicator=True)._merge.eq('both').all():
        raise ValueError('Forecast and blocked rows do not partition original roster')
    checks+=1
    evidence=pd.to_datetime(f.evidence_at,utc=True);cutoff=pd.to_datetime(f.cutoff,utc=True)
    latest=pd.to_datetime(f.history_latest_available_at,utc=True)
    if (evidence>cutoff).any() or (latest>cutoff).any():
        raise ValueError('Component state uses postdeadline evidence')
    rates=['goal_rate90','assist_rate90','dc_rate90','dc_opponent_factor','mu_dc','yellow_rate90','red_rate90']
    if not np.isfinite(f[rates].to_numpy(float)).all() or (f[rates]<0).any().any():
        raise ValueError('Invalid component rates')
    if ((f.p_yellow<0)|(f.p_red<0)|(f.p_yellow+f.p_red>1+1e-12)).any():
        raise ValueError('Invalid competing discipline probabilities')
    if not np.allclose(f.mu_dc,f.expected_minutes/90*f.dc_rate90*f.dc_opponent_factor,rtol=0,atol=1e-10):
        raise ValueError('DC exposure identity changed')
    if not (f.cold_start==(f.history_rows==0)).all():
        raise ValueError('Cold-start contract changed')
    checks+=5
    if not (pd.to_datetime(history.latest_guard_available_at,utc=True)<=pd.to_datetime(history.cutoff,utc=True)).all():
        raise ValueError('History summary uses postdeadline events')
    checks+=1
    report=dict(integrity_passed=True,checks=checks,player_rows=len(f),verified_first_entries=int(f.cold_start.sum()),
        blocked_roster_rows=len(blocked),blocked_fixtures=int(blocked.fixture_uuid.nunique()),
        common_player_components_available=True,full_roster_replay_ready=False,
        history_availability=m['source_history_availability'],team_goal_keeper_inputs_rebuilt=False)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
