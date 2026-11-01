"""Paired frozen-input diagnostics; never an independent holdout claim."""
import argparse, copy, gzip, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from test_separated_goal_head import decode
from fpl_v1_1_model.experimental_joint_role_assignment import RoleLineup
from fpl_v1_1_model.experimental_physical_timeline import PhysicalKernel
from precision_audit.return_p90 import ReturnP90Kernel, tilt_return_starts

ARMS = {'baseline': (1., 0.), 'return_only': (.5, 0.),
        'p90_only': (1., 2.), 'combined': (.5, 2.)}


def annotate_return_kinds(records, path):
    """Join only frozen predeadline episode features, never target labels."""
    columns = ['season', 'fixture_uuid', 'player_uuid', 'cutoff', 'return_kind',
               'return_active', 'max_history_known_at']
    features = pd.read_csv(path, usecols=columns)
    key = ['season', 'fixture_uuid', 'player_uuid']
    if features.duplicated(key).any():
        raise ValueError('Ambiguous frozen return feature identity')
    features = features.set_index(key)
    for r in records:
        for pid, meta in r['meta'].items():
            if not meta.get('return_active', False):
                continue
            f = features.loc[(r['season'], r['fixture_uuid'], pid)]
            cutoff = pd.Timestamp(r['cutoff'])
            if not f.return_active or pd.Timestamp(f.cutoff) != cutoff:
                raise ValueError('Frozen return episode/cutoff mismatch')
            if pd.notna(f.max_history_known_at) and pd.Timestamp(f.max_history_known_at) >= cutoff:
                raise ValueError('Future return feature')
            if f.return_kind not in ['medical_selection', 'suspension_selection']:
                raise ValueError('Unclassified return episode')
            meta['return_kind'] = f.return_kind


def kernels(record):
    inp = decode(copy.deepcopy(record['input']))
    dist = {int(k) if str(k).isdigit() else k:
            [v if isinstance(v, RoleLineup) else RoleLineup(**v) for v in vs]
            for k, vs in record['dist'].items()}
    returning = [p.player_id for p in inp.players if not p.is_keeper
                 and record['meta'].get(p.player_id, {}).get('return_kind') == 'medical_selection']
    result = {'baseline': PhysicalKernel(inp, dist)}
    for arm, (scale, floor) in ARMS.items():
        if arm != 'baseline':
            result[arm] = ReturnP90Kernel(inp, dist, returning=returning,
                                         return_scale=scale, regular_floor=floor)
    tilted, tilted_dist = tilt_return_starts(inp, dist, returning)
    result['return_start'] = PhysicalKernel(tilted, tilted_dist)
    result['return_start_p90'] = ReturnP90Kernel(tilted, tilted_dist, returning=returning,
                                               return_scale=1., regular_floor=.5)
    return inp, result


def evaluate(records):
    rows = []
    for i, r in enumerate(records):
        if not r.get('actual'):
            continue
        inp, arms = kernels(r)
        for arm, kernel in arms.items():
            for p in inp.players:
                if p.is_keeper or p.player_id not in r['actual']:
                    continue
                a = r['actual'][p.player_id]
                m = kernel.moments[p.player_id]
                rows.append(dict(season=r['season'], fixture_uuid=r['fixture_uuid'],
                    player_uuid=p.player_id, arm=arm,
                    returning=bool(r['meta'].get(p.player_id, {}).get('return_active', False)),
                    medical_return=r['meta'].get(p.player_id, {}).get('return_kind') == 'medical_selection',
                    suspension_return=r['meta'].get(p.player_id, {}).get('return_kind') == 'suspension_selection',
                    regular=p.p_start >= .9, actual_minutes=float(a['minutes']),
                    actual_start=float(a['started']), minutes=m['x'], p=m['p'],
                    p60=m['p60'], p90=m['p90']))
        if (i+1) % 10 == 0:
            print('kernels', i+1, '/', len(records), flush=True)
    return pd.DataFrame(rows)


def evaluate_parallel(records, workers):
    historical = [r for r in records if r.get('actual')]
    if workers == 1:
        return evaluate(historical)
    frames = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(evaluate, [r]) for r in historical]
        for i, future in enumerate(as_completed(futures)):
            frames.append(future.result())
            if (i+1) % 10 == 0 or i+1 == len(futures):
                print('historical fixtures', i+1, '/', len(futures), flush=True)
    return pd.concat(frames, ignore_index=True).sort_values(
        ['season', 'fixture_uuid', 'player_uuid', 'arm']).reset_index(drop=True)


def summaries(frame):
    rows = []
    for (season, arm), g in frame.groupby(['season', 'arm']):
        for name, keep in [('all_outfield', np.ones(len(g), bool)),
                           ('returning_proxy', g.returning), ('regular', g.regular),
                           ('medical_return', g.get('medical_return', pd.Series(False, index=g.index))),
                           ('suspension_return', g.get('suspension_return', pd.Series(False, index=g.index)))]:
            h = g[keep]
            if h.empty:
                continue
            rows.append(dict(season=season, arm=arm, group=name, rows=len(h),
                fixtures=h.fixture_uuid.nunique(), minute_mae=float(abs(h.minutes-h.actual_minutes).mean()),
                minute_bias=float((h.minutes-h.actual_minutes).mean()),
                start_brier=float(((h.p-h.actual_start)**2).mean()),
                p60_brier=float(((h.p60-h.actual_minutes.ge(60))**2).mean()),
                p90_brier=float(((h.p90-h.actual_minutes.eq(90))**2).mean()),
                p90_bias=float((h.p90-h.actual_minutes.eq(90)).mean())))
    return pd.DataFrame(rows)


def paired_points(records, draws):
    from fpl_v1_1_model.b_event_simulator import simulate_match
    rows = []
    # Fixed audit controls: all historical MC records, never selected by effect.
    for r in records:
        if not r.get('actual'):
            continue
        inp, arms = kernels(r)
        for seed in (20261102, 20261103):
            for arm, kernel in arms.items():
                total = np.zeros(len(inp.players))
                for draw in range(draws):
                    minute_rng = np.random.default_rng(np.random.SeedSequence([seed, draw, 1]))
                    event_rng = np.random.default_rng(np.random.SeedSequence([seed, draw, 2]))
                    result = simulate_match(inp, event_rng, timeline=kernel.sample(minute_rng))
                    total += [result[p.player_id].points for p in inp.players]
                for p, xp in zip(inp.players, total/draws):
                    if p.player_id not in r['actual'] or p.player_id.startswith('__'):
                        continue
                    rows.append(dict(season=r['season'], fixture_uuid=r['fixture_uuid'],
                        player_uuid=p.player_id, seed=seed, arm=arm, draws=draws,
                        xp=float(xp), actual=float(r['actual'][p.player_id]['total_points'])))
                print('points', r['season'], r['fixture_uuid'], seed, arm, flush=True)
    return pd.DataFrame(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--points-controls', type=Path)
    p.add_argument('--return-features', type=Path,
        default=Path('analysis/results/individual-mm-refinement-20261016/prior_only_features.csv.gz'))
    p.add_argument('--draws', type=int, default=2000)
    p.add_argument('--workers', type=int, default=1)
    a = p.parse_args()
    if a.draws < 2:
        p.error('At least two draws required')
    if not 1 <= a.workers <= 8:
        p.error('Workers must be between one and eight')
    sources = [Path(__file__), Path(__file__).with_name('return_p90.py'),
               Path('src/fpl_v1_1_model/experimental_physical_timeline.py'),
               Path('src/fpl_v1_1_model/b_event_simulator.py')]
    source_hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    records = json.loads(gzip.decompress(a.inputs.read_bytes()))
    annotate_return_kinds(records, a.return_features)
    f = evaluate_parallel(records, a.workers)
    if f.empty:
        raise ValueError('No historical outcomes: cannot measure accuracy')
    a.out.mkdir(parents=True, exist_ok=True)
    f.to_csv(a.out/'predictions.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    s = summaries(f)
    s.to_csv(a.out/'metrics.csv', index=False)
    manifest = dict(input_sha256=hashlib.sha256(a.inputs.read_bytes()).hexdigest(),
        source_sha256=source_hashes,
        hypotheses={**ARMS, 'return_start': {'log_odds': .5},
                    'return_start_p90': {'log_odds': .5, 'regular_floor': .5}},
        historical_fixtures=f.fixture_uuid.nunique(),
        scope='reused retrospective diagnostics; outfield only; no independent gain established',
        physical_clock='normalized 0..90, paired entries/exits; unchanged 900+90 team budget',
        label_clock='actual FPL reported minutes, never forced to sum 990',
        returning='medical_selection only is adjusted; suspension_selection reported separately',
        return_features_sha256=hashlib.sha256(a.return_features.read_bytes()).hexdigest(),
        production_active=False, ts_v3_changed=False)
    if a.points_controls:
        controls = json.loads(gzip.decompress(a.points_controls.read_bytes()))
        annotate_return_kinds(controls, a.return_features)
        q = paired_points(controls, a.draws)
        q.to_csv(a.out/'points-controls.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
        metrics = []
        for (season, arm, seed), h in q.groupby(['season', 'arm', 'seed']):
            metrics.append(dict(season=season, arm=arm, seed=int(seed), rows=len(h),
                mae=float(abs(h.xp-h.actual).mean()), bias=float((h.xp-h.actual).mean())))
        manifest['points_controls'] = metrics
        manifest['points_input_sha256'] = hashlib.sha256(a.points_controls.read_bytes()).hexdigest()
    if any(hashlib.sha256(path.read_bytes()).hexdigest() != source_hashes[str(path)] for path in sources):
        raise RuntimeError('Source changed during run; discard this evidence')
    (a.out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(s.to_string(index=False))
    print('METRICS_JSON='+s.to_json(orient='records'))
    if a.points_controls:
        print('POINTS_JSON='+json.dumps(manifest['points_controls']))


if __name__ == '__main__':
    main()
