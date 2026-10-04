"""Audit missing frozen components against pre-cutoff identity/registration evidence.

Read-only: does not synthesize registration, prices, outcomes or forecasts.
"""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import pandas as pd

from fpl_v1_1_model.paired_joint import read_frozen_table

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', type=Path, default=ROOT/'work/core.sqlite3')
    ap.add_argument('--out', type=Path, default=ROOT/'analysis/results/joint-cold-start-audit-v1')
    a = ap.parse_args()
    if a.out.exists():
        raise FileExistsError('Audit outputs are immutable; choose a new directory')
    folder = ROOT/'analysis/results/joint-paired-inputs-v1'
    missing = read_frozen_table(folder, 'missing_components')
    vpath = ROOT/'analysis/results/workload-recovered-minutes-v4/reused_holdout_diagnostic_predictions.csv.gz'
    v4 = pd.read_csv(vpath)
    keys = ['fixture_uuid', 'player_uuid']
    rows = missing.merge(v4[keys+['cutoff']], on=keys, how='left', validate='one_to_one')
    if rows.cutoff.isna().any():
        raise ValueError('Missing frozen cutoff')
    con = sqlite3.connect(a.db.resolve().as_uri()+'?mode=ro', uri=True)
    records = []
    for r in rows.sort_values(['gw', 'fixture_uuid', 'player_uuid']).itertuples(index=False):
        name = con.execute('SELECT canonical_name FROM players WHERE player_uuid=?', (r.player_uuid,)).fetchone()
        times = con.execute('SELECT DISTINCT kickoff_at FROM player_fixture_observations WHERE fixture_uuid=?', (r.fixture_uuid,)).fetchall()
        if len(times) != 1 or times[0][0] is None:
            raise ValueError('Missing or conflicting fixture kickoff')
        kickoff = times[0][0]
        if pd.Timestamp(r.cutoff) >= pd.Timestamp(kickoff):
            raise ValueError('Cutoff must precede target kickoff')
        prior = con.execute('''SELECT COUNT(DISTINCT fixture_uuid) FROM player_fixture_observations
            WHERE player_uuid=? AND season='2025-26' AND julianday(kickoff_at)<julianday(?)''',
            (r.player_uuid, r.cutoff)).fetchone()[0]
        first = con.execute('''SELECT MIN(kickoff_at) FROM player_fixture_observations
            WHERE player_uuid=? AND season='2025-26' ''', (r.player_uuid,)).fetchone()[0]
        reg_count, reg_before = con.execute('''SELECT COUNT(*),
            SUM(CASE WHEN julianday(observed_at)<=julianday(?) AND julianday(valid_from)<=julianday(?)
                AND (valid_to IS NULL OR julianday(valid_to)>julianday(?)) AND active=1 THEN 1 ELSE 0 END)
            FROM player_registrations WHERE player_uuid=? AND season='2025-26' AND team_id=?''',
            (r.cutoff, r.cutoff, r.cutoff, r.player_uuid, r.team_id)).fetchone()
        state_before = con.execute('''SELECT COUNT(*) FROM player_state_snapshots
            WHERE player_uuid=? AND season='2025-26' AND team_id=?
            AND julianday(observed_at)<=julianday(?)''', (r.player_uuid, r.team_id, r.cutoff)).fetchone()[0]
        records.append(dict(fixture_uuid=r.fixture_uuid, player_uuid=r.player_uuid,
            canonical_name=name[0] if name else None, gw=r.gw, team_id=r.team_id, position=r.pos,
            cutoff=r.cutoff, kickoff=kickoff, first_season_observation=first,
            prior_season_fixtures=prior, registration_rows=reg_count,
            active_registration_rows_before_cutoff=int(reg_before or 0),
            state_rows_before_cutoff=state_before, missing_components=r.missing_components,
            recovery_status='blocked_no_prior_history_or_registration' if not prior and not reg_before
                else 'requires_review'))
    audited = pd.DataFrame(records)
    inventory = {}
    for table in ['player_registrations', 'player_state_snapshots']:
        inventory[table] = [dict(season=s, rows=n, earliest_observed_at=lo, latest_observed_at=hi)
            for s, n, lo, hi in con.execute(f'SELECT season,COUNT(*),MIN(observed_at),MAX(observed_at) FROM {table} GROUP BY season')]
    con.close()
    a.out.mkdir(parents=True)
    csv = a.out/'missing_rows.csv'
    audited.to_csv(csv, index=False, lineterminator='\n')
    sources = [folder/'manifest.json', vpath, ROOT/'analysis/results/joint-component-recovery-v1/manifest.json', Path(__file__)]
    result = dict(season='2025-26', classification='input_audit_not_new_holdout',
        missing_rows=len(audited), affected_fixtures=int(audited.fixture_uuid.nunique()),
        unique_players=int(audited.player_uuid.nunique()),
        no_prior_season_history=int((audited.prior_season_fixtures == 0).sum()),
        no_asof_registration=int((audited.active_registration_rows_before_cutoff == 0).sum()),
        no_asof_player_state=int((audited.state_rows_before_cutoff == 0).sum()),
        original_parameters_available=True, full_roster_replay_ready=False,
        table_inventory=inventory, database_sha256=sha(a.db),
        sources=[dict(path=str(p.relative_to(ROOT)), sha256=sha(p)) for p in sources],
        output=dict(path='missing_rows.csv', sha256=sha(csv)),
        findings=[
            'Original Phase3C/3D/3E predictors skip players with empty current-season minutes history.',
            'Frozen parameters alone do not restore forecasts for those first-entry rows.',
            'Postmatch merged-GW presence and a synthetic deadline timestamp do not prove predeadline registration.',
            'Current-season position priors are available mathematically, but enabling a cold-start path extends the frozen model contract.',
            'Adding attack propensities changes within-team normalization; a future complete-roster comparison needs a new paired checkpoint.'],
        required_inputs=[
            'Archived 2025/26 predeadline squad/registration snapshots with player/team/position and source timestamps, including the 46 first-entry rows.',
            'Predeadline FPL player-state/price snapshots and fixture/deadline horizon for full season replay.',
            'A separately versioned first-entry component contract using recovered frozen position shrinkage parameters; no target fitting.'],
        unchanged='Original simulator, adapter, control/v4 diagnostic and transfer/chip policy')
    (a.out/'manifest.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps({k:result[k] for k in ['missing_rows','affected_fixtures','no_prior_season_history','no_asof_registration','no_asof_player_state','full_roster_replay_ready']}, indent=2))


if __name__ == '__main__':
    main()
