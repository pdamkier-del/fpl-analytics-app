"""Read-only finishing/receiver feasibility audit; no model promotion or forecasts."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research_pm_conversion import observations
from fpl_v1_1_model.experimental_elite_finishing import finishing_estimates


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--db', default='work/core.sqlite3')
    parser.add_argument('--live-history', required=True)
    parser.add_argument('--forecast', required=True)
    parser.add_argument('--pm-input', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    forecast = json.loads(Path(args.forecast).read_text())
    cut = pd.Timestamp(forecast['data_asof'])
    history, _, _, source_audit = observations(args.db)
    live = pd.read_csv(args.live_history, low_memory=False)
    live['known'] = pd.to_datetime(live.available_at, utc=True)
    if set(live.season) != {forecast['season']} or live.gw.ge(min(forecast['gws'])).any():
        raise ValueError('Live history must precede the forecast horizon')
    if live.known.isna().any() or live.known.ge(cut).any():
        raise ValueError('Unavailable live observations')
    history = pd.concat([history, live], ignore_index=True)
    if history.duplicated(['season', 'fixture_uuid', 'player_uuid']).any():
        raise ValueError('Overlapping history')
    history = history[history.known.lt(cut)]
    ids = [p['player_uuid'] for p in forecast['players']]
    people = {p['player_uuid']: p for p in forecast['players']}
    # Web names are not unique (there is another Palmer in this catalogue).
    focus = [p for p in people.values() if p['id'] in (12, 154)]
    if {(p['name'], p['team']) for p in focus} != {('Saka', 'Arsenal'), ('Palmer', 'Chelsea')}:
        raise ValueError('Focus identity mismatch')
    estimates = {str(half): finishing_estimates(history, cut, ids, half_life_days=half)
                 for half in (90., 365., 730.)}
    pm = pd.read_csv(args.pm_input, low_memory=False)
    rows = []
    for person in focus:
        pid = person['player_uuid']
        past = history[history.player_uuid.eq(pid)]
        fx = person['weeks'][0]['fixtures'][0]['fixture_uuid']
        teammates = pm[pm.fixture_uuid.eq(fx) & pm.team_id.eq(person['team_id'])
                       & pm.player_uuid.ne(pid)]
        weights, theta = [], []
        for r in teammates.itertuples():
            player = people.get(r.player_uuid)
            if player is None:
                raise ValueError('Missing forecast player')
            fixture = next(f for w in player['weeks'] for f in w['fixtures']
                           if f['fixture_uuid'] == fx)
            weights.append(r.goal_rate90 * fixture['pm_analytic_minutes'] / 90.)
            theta.append(estimates['730.0'][r.player_uuid]['factor'])
        if sum(weights) <= 0:
            raise ValueError('Missing receiver chance mass')
        rows.append(dict(name=person['name'], player_uuid=pid,
                         goals=float(past.goals.sum()), xg=float(past.xg.sum()),
                         finishing={h: e[pid] for h, e in estimates.items()},
                         receiver_proxy=float(np.average(theta, weights=weights)),
                         receiver_proxy_definition='goal-rate × PM expected exposure, excluding creator; not observed pass→shot links'))
    verified = []
    for directory in ('pm-research-20261015', 'player-pm-v2-20261015', 'dynamic-pm-v2-20261015'):
        root = Path('analysis/results') / directory
        manifest = json.loads((root / 'evidence_manifest.json').read_text())
        entries = manifest.get('files')
        if entries is None:
            entries = [dict(file=k, sha256=v) for k, v in manifest['original_export_sha256'].items()]
        for entry in entries:
            path = root / entry['file']
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                raise ValueError('Research evidence checksum mismatch: ' + str(path))
            verified.append(str(path))
    # A common receiver multiplier cancels under fixed-total normalization.
    a = np.array([.4, .3, .2, .1])
    assert np.allclose(a / a.sum(), (a * 1.2) / (a * 1.2).sum())
    report = dict(classification='FEASIBILITY_AND_SENSITIVITY_NOT_ACCURACY_TEST',
                  forecast_sha256=forecast['forecast_sha256'], cutoff=str(cut),
                  source_audit=source_audit, focus=rows, verified_prior_reports=verified,
                  common_multiplier_cancels_under_fixed_total=True,
                  limitations=['All-xG finishing includes penalties; not identified non-penalty ability',
                               'Receiver proxy has no observed creator links or sampled co-presence',
                               'No new historical accuracy or candidate xP gain claimed',
                               'Prior historical evaluation periods reused; not independent holdouts'],
                  production_changed=False, promotion_allowed=False)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'focus': rows, 'verified_reports': len(verified)}, indent=2))


if __name__ == '__main__':
    main()
