#!/usr/bin/env python3
"""Run one real B->PM match, then one GW, before the existing six-GW run.

Uses exactly the existing B inference, attachment and locked PM simulator.
Seeds are indexed by the full horizon, so later checks are bit-comparable.
"""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from mm_candidate_forecast import infer_B
from mm_locked_bridge import attach_mm
from run_live_vfinal_joint_simulation import simulate


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--inputs', type=Path, default=Path('work/current-B-inputs'))
    p.add_argument('--out', type=Path, default=Path('work/current-B-stages.json'))
    a = p.parse_args()
    history = pd.read_csv(a.inputs/'history.csv.gz')
    target = pd.read_csv(a.inputs/'target.csv.gz')
    provenance = json.loads((a.inputs/'provenance.json').read_text())
    predicted, _ = infer_B(history, target, provenance)
    joined = attach_mm(pd.read_csv(a.inputs/'pm.csv.gz'), predicted)
    offsets = {f:i for i,f in enumerate(sorted(joined.fixture_uuid.unique()))}
    origin = int(joined.gw.min())
    first = joined[joined.gw.eq(origin)].sort_values(['target_kickoff','fixture_uuid']).iloc[0].fixture_uuid
    results = []
    for name, mask in [('one-match', joined.fixture_uuid.eq(first)), ('one-gw', joined.gw.eq(origin))]:
        frame = joined.loc[mask].copy()
        xp, audit = simulate(frame, fixture_seed_offsets=offsets, minute_sampler='locked')
        if not audit['point_components_reconciled'] or len(xp) != len(frame):
            raise ValueError('Incomplete B -> locked PM stage: '+name)
        canonical = xp.sort_values(['fixture_uuid','player_uuid']).to_json(orient='records',double_precision=15)
        results.append(dict(scope=name, gw=origin, fixtures=int(frame.fixture_uuid.nunique()),
            player_fixture_rows=len(frame), minute_sampler='locked', point_components_reconciled=True,
            output_sha256=hashlib.sha256(canonical.encode()).hexdigest()))
        print(json.dumps(results[-1]), flush=True)
    a.out.write_text(json.dumps(dict(data_asof=provenance['data_at'],stages=results),indent=2)+'\n')


if __name__ == '__main__':
    main()
