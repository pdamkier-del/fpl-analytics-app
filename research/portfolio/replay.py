"""Retrospective variogram diagnostic for the earlier, reconstructed PM archive."""
from collections import defaultdict
from datetime import datetime
import gzip
import hashlib
from itertools import combinations
import json
from pathlib import Path

import numpy as np

from correlations import category


def variogram_loss(a, b, actual_a, actual_b):
    return float((np.sqrt(abs(actual_a-actual_b)) - np.sqrt(np.abs(a-b)).mean())**2)


def evaluate(root, rng):
    manifest = json.loads((root/'manifest.json').read_text())

    def load(name):
        payload = (root/name).read_bytes()
        if hashlib.sha256(payload).hexdigest() != manifest['files'][name]:
            raise ValueError(f'Replay input hash mismatch: {name}')
        return json.loads(gzip.decompress(payload))

    outcomes = load('history/match-results.json.gz')
    labels = {(r['gw'], r['fixture_id'], r['player_id']): r for r in outcomes['match_rows']
              if not r['provisional']}
    metrics = {}
    for gw in manifest['gws']:
        forecast = load(f'gw{gw}/forecast.json.gz')
        scenarios = load(f'gw{gw}/scenarios.json.gz')
        if (forecast['cutoff'] != scenarios['cutoff'] or forecast['gw'] != gw
                or scenarios['gw'] != gw or gw not in outcomes['completed_gws']
                or forecast['model_source'] != manifest['model_source']
                or datetime.fromisoformat(forecast['cutoff']) >=
                datetime.fromisoformat(forecast['origin_deadline'])):
            raise ValueError('Replay identity or cutoff mismatch')
        points = {(r['fixture_uuid'], r['player_uuid']): np.array(r['scenarios']['points'])
                  for r in scenarios['records']}
        fixtures = defaultdict(list)
        missing = 0
        for p in forecast['players']:
            if p['p_play'] < .5:
                continue
            fx = p['fixture_uuid']
            label = labels.get((gw, int(fx.rsplit('-', 1)[1]), p['player_id']))
            if label is None or label['team_id'] != p['team_id']:
                missing += 1
                continue
            draws = points[fx, p['player_uuid']]
            if len(draws) != forecast['draws'] or not np.isclose(draws.mean(), p['xp']):
                raise ValueError('Replay mean or draw count mismatch')
            fixtures[fx].append((p, draws, label['total_points']))
        loss = defaultdict(list)
        fixture_scores = []
        for group in fixtures.values():
            current = []
            for (a, draws_a, actual_a), (b, draws_b, actual_b) in combinations(group, 2):
                key = category(a['position'], b['position'], a['team_id'] == b['team_id'], True)
                joint = variogram_loss(draws_a, draws_b, actual_a, actual_b)
                independent = np.mean([variogram_loss(draws_a, rng.permutation(draws_b),
                                                      actual_a, actual_b) for _ in range(8)])
                values = (joint, independent)
                current.append(values)
                if key:
                    loss[key].append(values)
            if current:
                fixture_scores.append(np.mean(current, axis=0))
        scores = np.asarray(fixture_scores)
        metrics[gw] = dict(fixtures=len(scores), predicted_players_missing_join=missing,
                           joint=float(scores[:, 0].mean()),
                           independent=float(scores[:, 1].mean()),
                           categories={key: dict(pairs=len(values),
                                                joint=float(np.mean(values, axis=0)[0]),
                                                independent=float(np.mean(values, axis=0)[1]))
                                       for key, values in loss.items()})
    return dict(model_source=manifest['model_source'], weeks=metrics,
                manifest_sha256=hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest())
