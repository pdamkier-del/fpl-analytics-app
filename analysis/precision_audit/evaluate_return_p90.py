"""Paired frozen-input diagnostics; never an independent holdout claim."""
import argparse, copy, gzip, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
from test_separated_goal_head import decode
from fpl_v1_1_model.experimental_joint_role_assignment import RoleLineup
from fpl_v1_1_model.experimental_physical_timeline import PhysicalKernel
from precision_audit.return_p90 import ReturnP90Kernel

ARMS = {'baseline': (1., 0.), 'return_only': (.5, 0.),
        'p90_only': (1., 2.), 'combined': (.5, 2.)}


def kernels(record):
    inp = decode(copy.deepcopy(record['input']))
    dist = {int(k) if str(k).isdigit() else k:
            [v if isinstance(v, RoleLineup) else RoleLineup(**v) for v in vs]
            for k, vs in record['dist'].items()}
    returning = [p.player_id for p in inp.players if not p.is_keeper
                 and record['meta'].get(p.player_id, {}).get('return_active', False)]
    result = {'baseline': PhysicalKernel(inp, dist)}
    for arm, (scale, floor) in ARMS.items():
        if arm != 'baseline':
            result[arm] = ReturnP90Kernel(inp, dist, returning=returning,
                                         return_scale=scale, regular_floor=floor)
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
                    regular=p.p_start >= .9, actual_minutes=float(a['minutes']),
                    actual_start=float(a['started']), minutes=m['x'], p=m['p'],
                    p60=m['p60'], p90=m['p90']))
        if (i+1) % 10 == 0:
            print('kernels', i+1, '/', len(records), flush=True)
    return pd.DataFrame(rows)


def summaries(frame):
    rows = []
    for (season, arm), g in frame.groupby(['season', 'arm']):
        for name, keep in [('all_outfield', np.ones(len(g), bool)),
                           ('returning_proxy', g.returning), ('regular', g.regular)]:
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
    p.add_argument('--draws', type=int, default=2000)
    a = p.parse_args()
    if a.draws < 2:
        p.error('At least two draws required')
    records = json.loads(gzip.decompress(a.inputs.read_bytes()))
    f = evaluate(records)
    if f.empty:
        raise ValueError('No historical outcomes: cannot measure accuracy')
    a.out.mkdir(parents=True, exist_ok=True)
    f.to_csv(a.out/'predictions.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    s = summaries(f)
    s.to_csv(a.out/'metrics.csv', index=False)
    manifest = dict(input_sha256=hashlib.sha256(a.inputs.read_bytes()).hexdigest(),
        source_sha256={str(Path(__file__).name): hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'return_p90.py': hashlib.sha256(Path(__file__).with_name('return_p90.py').read_bytes()).hexdigest()},
        hypotheses=ARMS, historical_fixtures=f.fixture_uuid.nunique(),
        scope='reused retrospective diagnostics; outfield only; no independent gain established',
        physical_clock='normalized 0..90, paired entries/exits; unchanged 900+90 team budget',
        label_clock='actual FPL reported minutes, never forced to sum 990',
        returning='existing return_active proxy includes medical and suspension episodes',
        production_active=False, ts_v3_changed=False)
    if a.points_controls:
        controls = json.loads(gzip.decompress(a.points_controls.read_bytes()))
        q = paired_points(controls, a.draws)
        q.to_csv(a.out/'points-controls.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
        metrics = []
        for (season, arm, seed), h in q.groupby(['season', 'arm', 'seed']):
            metrics.append(dict(season=season, arm=arm, seed=int(seed), rows=len(h),
                mae=float(abs(h.xp-h.actual).mean()), bias=float((h.xp-h.actual).mean())))
        manifest['points_controls'] = metrics
        manifest['points_input_sha256'] = hashlib.sha256(a.points_controls.read_bytes()).hexdigest()
    (a.out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(s.to_string(index=False))


if __name__ == '__main__':
    main()
