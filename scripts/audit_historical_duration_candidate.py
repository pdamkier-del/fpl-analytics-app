#!/usr/bin/env python3
"""Prepare an opt-in duration shadow, refusing unmatched archived baselines.

No locked coefficients or source files are overwritten. The selected half-life
comes from the separate 2024 development experiment, not this test period.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fpl_v1_1_model.minutes import project_minutes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', required=True)
    ap.add_argument('--mm', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    report_path = ROOT / 'analysis/results/full-model-audit-20261012/duration_walkforward_report.json'
    experiment = json.loads(report_path.read_text())
    original_h = experiment['original_half_life']
    selected_h = experiment['selected_half_life']
    mm = pd.read_csv(args.mm)
    if mm.duplicated(['fixture_uuid', 'player_uuid']).any():
        raise ValueError('Duplicate archived identities')
    with sqlite3.connect(f'file:{Path(args.db).resolve()}?mode=ro', uri=True) as con:
        obs = pd.read_sql_query("SELECT fixture_uuid,player_uuid,gw,kickoff_at,started,minutes FROM player_fixture_observations WHERE season='2025-26' AND is_final=1", con)
    if obs.duplicated(['fixture_uuid', 'player_uuid']).any() or obs[['started','minutes','kickoff_at']].isna().any().any():
        raise ValueError('Missing or duplicate historical observations')
    obs['available_at'] = pd.to_datetime(obs.kickoff_at, utc=True) + pd.Timedelta(hours=3)
    histories = {str(pid): g.sort_values(['available_at','fixture_uuid']) for pid,g in obs.groupby('player_uuid')}
    values = []
    original_values = []
    no_history_unchanged = 0
    for r in mm.itertuples(index=False):
        g = histories[str(r.player_uuid)]
        prior = g[g.available_at < pd.Timestamp(r.cutoff)]
        if prior.empty:
            # Preserve the archived cold-start output; do not fit or invent one.
            values.append(float(r.new_start_minutes))
            original_values.append(float(r.new_start_minutes))
            no_history_unchanged += 1
            continue
        history = prior[['started','minutes']].to_dict('records')
        original_values.append(project_minutes(history, duration_half_life=original_h).expected_minutes_given_start)
        values.append(project_minutes(history, duration_half_life=selected_h).expected_minutes_given_start)
    delta = np.asarray(original_values) - mm.new_start_minutes.to_numpy()
    if not np.all(np.abs(delta) < 1e-10):
        raise ValueError(f'Archived duration reconstruction failed: {np.max(np.abs(delta))}')
    candidate = mm.copy()
    candidate['new_start_minutes'] = values
    candidate['new_xmins'] = candidate.new_p_start * candidate.new_start_minutes + (1-candidate.new_p_start)*candidate.new_q_sub*candidate.new_sub_minutes
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    candidate.to_csv(out/'candidate_mm.csv.gz', index=False, compression='gzip')
    report = dict(classification='PAIRED_DURATION_COMPONENT_SHADOW_NOT_CERTIFICATION', rows=len(mm), no_history_archived_duration_retained=no_history_unchanged, original_half_life=original_h, selected_half_life=selected_h, max_baseline_duration_difference=float(np.max(np.abs(delta))), source_sha256=hashlib.sha256(Path(args.mm).read_bytes()).hexdigest(), selection=experiment['selection'], availability='kickoff+3h historical replay proxy, not verified publication timestamps', unchanged=['p_start','p_cameo_given_bench','cameo_minutes','all locked model source'], promotion_allowed=False)
    (out/'preparation_report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
