#!/usr/bin/env python3
"""Tune only six horizon weights and the paid-transfer uncertainty buffer.

Calls the frozen HEAD replay/planner directly. Each worker is an isolated
process; parallel scheduling does not change candidate/search mechanics.
"""
from __future__ import annotations

import argparse
import contextlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
import run_transfer_strategy_v3_replay as replay
from fpl_xpts.transfer_planner import PlannerConfig

HEAD = '08fc9670f1b6aedfeed1851effdfd0e721db6e91'
OUT = ROOT / 'analysis/results/ts-v3-weight-buffer-grid-20261005-v1'
BASE = ROOT / 'analysis/results/transfer-strategy-v3-replay-20261005-v2'
MANUAL = [
    ('manual_baseline', (1.00, .85, .70, .55, .40, .25)),
    ('manual_085_065', (1.00, .85, .65, .45, .30, .20)),
    ('manual_080_060', (1.00, .80, .60, .40, .25, .15)),
    ('manual_075_055', (1.00, .75, .55, .40, .25, .15)),
    ('manual_070_045', (1.00, .70, .45, .30, .20, .10)),
]
WEIGHTINGS = [dict(name=n, family='manual', rho=None, weights=list(w)) for n, w in MANUAL]
WEIGHTINGS += [dict(name=f'exp_{rho:.2f}', family='exponential', rho=rho,
                    weights=[rho ** k for k in range(6)])
               for rho in (.60, .65, .70, .75, .80, .85, .90)]
JOBS = [dict(**w, buffer=b, label=f"{w['name']}_buffer_{b:.1f}")
        for w in WEIGHTINGS for b in (1.0, 1.5, 2.0)]
DATA = None


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def frozen_inputs():
    paths = [p for folder in ('src', 'model') for p in (ROOT / folder).rglob('*')
             if p.is_file() and '__pycache__' not in str(p) and p.suffix in ('.py', '.json')]
    paths += [ROOT / 'scripts' / n for n in (
        'run_transfer_strategy_v3_replay.py', 'run_horizon_policy_comparison.py',
        'run_transfer_strategy_v2_grid.py')]
    for folder in ('legacy-rolling-recovery-v1', 'legacy-season-technical-replay-v1'):
        base = ROOT / 'analysis/results' / folder
        paths += [p for p in base.iterdir() if '.part-' in p.name or 'manifest' in p.name]
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(paths))}


def init_worker():
    global DATA
    # fork shares the read-only input frames; spawn remains supported.
    if DATA is None:
        DATA = replay.prepare()


def run_job(job):
    folder = OUT / job['label']
    folder.mkdir(parents=True, exist_ok=True)
    params = folder / 'parameters.json'
    if params.exists():
        if json.loads(params.read_text()) != job:
            raise RuntimeError('Parameter mismatch: ' + job['label'])
    else:
        write_json(params, job)
    result_path = folder / 'result.json'
    if result_path.exists():
        return json.loads(result_path.read_text())
    replay.WEIGHTS = tuple(job['weights'])
    replay.BUFFER = job['buffer']
    replay.OUT = folder
    start, cpu_start = time.perf_counter(), time.process_time()
    with (folder / 'run.log').open('a') as log, contextlib.redirect_stdout(log):
        result = replay.run_v3(*DATA)
    logs = pd.DataFrame(result.pop('logs'))
    result.pop('plans')  # complete paths are already saved by the frozen replay
    early, late = logs[logs.gw <= 21], logs[logs.gw >= 22]
    initial = json.loads((folder / 'checkpoint.json').read_text())['initial']
    row = dict(**job, **result,
               points_gw1_21=int(early.score.sum()), points_gw22_38=int(late.score.sum()),
               transfers_gw1_21=int(early.transfers.sum()), transfers_gw22_38=int(late.transfers.sum()),
               hits_gw1_21=int(early.hit_cost.sum()), hits_gw22_38=int(late.hit_cost.sum()),
               forced_transfers=int(logs.forced_transfers.sum()),
               initial_squad=initial,
               invocation_wall_seconds=time.perf_counter() - start,
               invocation_cpu_seconds=time.process_time() - cpu_start)
    assert len(logs) == 38 and logs.gw.tolist() == list(range(1, 39))
    assert row['total_points'] == row['points_gw1_21'] + row['points_gw22_38']
    write_json(result_path, row)
    return row


def summarize(rows, wall_seconds, protocol):
    if not rows:
        return
    tab = pd.DataFrame(rows)
    baseline = json.loads((BASE / 'summary.json').read_text())
    b3, b2 = baseline['ts_v3'], baseline['ts_v2_comparator']
    b3logs = pd.read_csv(BASE / 'tsv3_gameweek_log.csv')
    b2logs = pd.read_csv(BASE / 'tsv2_gameweek_log.csv')
    for metric in ('total_points', 'transfers', 'hit_points', 'uplift'):
        tab[f'delta_{metric}_vs_v3'] = tab[metric] - b3[metric]
        tab[f'delta_{metric}_vs_v2'] = tab[metric] - b2[metric]
    for name, logs in (('v3', b3logs), ('v2', b2logs)):
        tab[f'delta_dev_vs_{name}'] = tab.points_gw1_21 - int(logs[logs.gw <= 21].score.sum())
        tab[f'delta_late_vs_{name}'] = tab.points_gw22_38 - int(logs[logs.gw >= 22].score.sum())
    for metric, suffix in (('total_points', 'season'), ('points_gw1_21', 'dev'), ('points_gw22_38', 'late')):
        tab[f'rank_{suffix}'] = tab[metric].rank(method='min', ascending=False).astype(int)
    tab['recovered_gap_fraction'] = tab.delta_total_points_vs_v3 / 145.0
    tab['beats_baseline_both_periods'] = (tab.delta_dev_vs_v3 > 0) & (tab.delta_late_vs_v3 > 0)
    tab['top10_both_periods'] = (tab.rank_dev <= 10) & (tab.rank_late <= 10)
    tab['worst_period_gain_per_gw'] = pd.concat([
        tab.delta_dev_vs_v3 / 21, tab.delta_late_vs_v3 / 17], axis=1).min(axis=1)
    tab['weights'] = tab.weights.apply(lambda w: json.dumps(w))
    tab = tab.sort_values(['total_points', 'hit_points', 'transfers', 'label'], ascending=[False, True, True, True])
    tab.to_csv(OUT / 'ranking.csv', index=False)
    for group, filename in (('buffer', 'mean_by_buffer.csv'), ('name', 'mean_by_weighting.csv'), ('family', 'mean_by_family.csv')):
        agg = tab.groupby(group).agg(
            count=('total_points', 'size'), mean_points=('total_points', 'mean'),
            min_points=('total_points', 'min'), max_points=('total_points', 'max'),
            mean_dev=('points_gw1_21', 'mean'), mean_late=('points_gw22_38', 'mean'),
            mean_transfers=('transfers', 'mean'), mean_hit_points=('hit_points', 'mean'),
            mean_uplift=('uplift', 'mean'), mean_runtime=('runtime_seconds', 'mean'),
        ).reset_index()
        agg.to_csv(OUT / filename, index=False)
    dev = tab.sort_values(['points_gw1_21', 'hits_gw1_21', 'transfers_gw1_21', 'label'],
                         ascending=[False, True, True, True])
    late = tab.sort_values(['points_gw22_38', 'hits_gw22_38', 'transfers_gw22_38', 'label'],
                          ascending=[False, True, True, True])
    summary = dict(
        classification='TS v3 parameter grid; recovered Phase5Q strategy proxy; chips OFF',
        completed=len(rows), expected=len(JOBS), all_complete=len(rows) == len(JOBS),
        starting_head=HEAD, experiment_wall_seconds=wall_seconds,
        selection_rule=protocol['selection_rule'], development_choice=dev.iloc[0].to_dict(),
        later_period_optimum=late.iloc[0].to_dict(), hindsight_season_maximum=tab.iloc[0].to_dict(),
        optimum_switches=dev.iloc[0]['label'] != late.iloc[0]['label'],
        beats_baseline_both_periods=tab[tab.beats_baseline_both_periods].label.tolist(),
        top10_both_periods=tab[tab.top10_both_periods].label.tolist(),
        baseline_v3=b3, comparator_v2=b2,
        temporal_caveat='GW22–38 is a later diagnostic, not an untouched holdout: this season and Phase5Q have been inspected previously. Full-season maxima and robustness rankings are exploratory; development choice is based only on GW1–21. Later totals reflect state carried from GW1–21, not a reset squad.',
    )
    # pandas represents rho=None as NaN; replace it before strict JSON output.
    for key in ('development_choice', 'later_period_optimum', 'hindsight_season_maximum'):
        summary[key] = {k: (None if isinstance(v, float) and pd.isna(v) else v)
                        for k, v in summary[key].items()}
    write_json(OUT / 'summary.json', summary)


def main():
    global DATA
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    frozen = frozen_inputs()
    protocol = dict(starting_head=HEAD, jobs=JOBS, workers=args.workers,
        grid_script_sha256=digest(__file__), frozen_sources_and_inputs=frozen,
        locked_config=asdict(PlannerConfig(beam_width=20, candidates_per_transfer_count=1, milp_time_limit=2.0)),
        selection_rule='Max GW1–21 actual net points; ties: fewer GW1–21 hit points, fewer GW1–21 transfers, then lexicographic label. GW22–38 is evaluated after this choice; no reset at GW22.',
        scope='Only weights and paid-transfer uncertainty buffer vary. Frozen run_v3 is invoked without code or search modifications.')
    pp = OUT / 'protocol.json'
    if pp.exists():
        if json.loads(pp.read_text()) != protocol:
            raise RuntimeError('Protocol/code/input mismatch; do not mix experiments')
    else:
        write_json(pp, protocol)
    DATA = replay.prepare()
    start = time.perf_counter()
    rows = []
    # The worker starts from exactly the same frozen initial optimization and
    # actual-point engine as the baseline; only the two globals vary.
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=mp.get_context('fork'),
                             initializer=init_worker) as pool:
        futures = {pool.submit(run_job, job): job for job in JOBS}
        for f in as_completed(futures):
            row = f.result()
            rows.append(row)
            summarize(rows, time.perf_counter() - start, protocol)
            print(f"{len(rows)}/{len(JOBS)} {row['label']}: {row['total_points']} pts; "
                  f"dev {row['points_gw1_21']}, late {row['points_gw22_38']}", flush=True)
    if frozen_inputs() != frozen:
        raise RuntimeError('Locked sources/inputs changed during experiment')
    initial = json.loads((BASE / 'checkpoint.json').read_text())['initial']
    assert all(r['initial_squad'] == initial for r in rows)
    assert all(r['no_transfer_control'] == 1425 for r in rows)
    base = next(r for r in rows if r['label'] == 'manual_baseline_buffer_1.5')
    assert (base['total_points'], base['transfers'], base['hit_points']) == (1992, 45, 32)
    summarize(rows, time.perf_counter() - start, protocol)
    write_json(OUT / 'verification.json', dict(
        frozen_sources_and_inputs_unchanged=True, all_36_complete=True,
        same_initial_squad=True, same_no_transfer_control=True,
        baseline_reproduced=True, point_model_unchanged=True, ts_v3_mechanics_unchanged=True,
        forced_transfers_by_combination={r['label']: r['forced_transfers'] for r in rows}))
    outputs = [p for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'manifest.json']
    write_json(OUT / 'manifest.json', dict(sources=[dict(path=str(Path(__file__).relative_to(ROOT)), sha256=digest(__file__))],
        outputs=[dict(path=str(p.relative_to(OUT)), sha256=digest(p)) for p in outputs]))


if __name__ == '__main__':
    main()
