"""Post-hoc diagnosis of the rejected trial; never changes its gates or model."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    predictions = pd.read_csv(args.predictions)
    with sqlite3.connect(args.db.resolve().as_uri() + '?mode=ro', uri=True) as con:
        observations = pd.read_sql_query(
            "SELECT season, fixture_uuid, player_uuid, fpl_red_cards "
            "FROM player_fixture_observations WHERE is_final=1 "
            "AND season IN ('2024-25','2025-26')", con)
    red = observations.groupby(['season', 'fixture_uuid']).fpl_red_cards.max()
    predictions['removal_context'] = [
        'unknown_red_card_context' if pd.isna(red.get((season, fixture)))
        else 'recorded_red_card' if red.get((season, fixture)) > 0
        else 'no_recorded_red_card'
        for season, fixture in zip(predictions.season, predictions.fixture_uuid)]
    groups = []
    for (season, context, arm), rows in predictions.groupby(['season', 'removal_context', 'arm']):
        groups.append(dict(season=season, context=context, arm=arm,
            fixtures=int(rows.fixture_uuid.nunique()), player_rows=len(rows),
            minute_MAE=float(np.abs(rows.xmins-rows.minutes).mean()),
            minute_bias=float((rows.xmins-rows.minutes).mean()),
            xP_MAE=float(np.abs(rows.xp-rows.total_points).mean())))
    result = dict(scope='Post-hoc diagnosis only; original all-fixture rejection and gates unchanged',
        source='Read-only Core final observations. No recorded red card does not prove all removal events absent.',
        predictions_sha256=hashlib.sha256(args.predictions.read_bytes()).hexdigest(),
        dismissal_context_sha256=hashlib.sha256(red.sort_index().to_csv().encode()).hexdigest(),
        independent_validation=False, candidate_activated=False, groups=groups)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
