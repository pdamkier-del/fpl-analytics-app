"""Fixed-protocol finishing/receiver ablation on original historical PM inputs."""
import argparse
import copy
from contextlib import nullcontext
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from audit_capture_io import checked_records, write_records, write_frame
from audit_correctness_historical import decode
from experiment_mm_pm import POINT_COMPONENTS
from replay_pm_conversion import simulate_observed, summarize
from research_pm_conversion import observations, deadlines, target_records, weighted_states, factors
from fpl_v1_1_model.experimental_pm_conversion import event_weights
from fpl_v1_1_model.experimental_receiver_conversion import shadow_receiver_conversion

ROOT = Path(__file__).resolve().parents[1]
MODES = ('original', 'individual', 'receivers', 'combined')


def evaluate(task):
    record, directory, fingerprint, draws = task
    signature = hashlib.sha256(json.dumps([record, fingerprint, draws], sort_keys=True).encode()).hexdigest()
    path = Path(directory) / (record['core_fixture'] + '.jsonl.gz')
    if path.exists():
        cached = checked_records(path)[0]
        if cached['signature'] == signature:
            return cached['rows']
    base = decode(copy.deepcopy(record['input']))
    gf = record['factors']
    rows = []
    for mode in MODES:
        inp = event_weights(base, gf) if mode in ('individual', 'combined') else base
        context = shadow_receiver_conversion(base, gf) if mode in ('receivers', 'combined') else nullcontext()
        with context:
            sim = simulate_observed(inp, record['seed'], draws=draws)
        if mode == 'original' and draws == 400:
            if any(sim[pid]['xPts'] != xp for pid, xp in record['reference'].items()):
                raise ValueError('Original xP not reproduced exactly')
        for p in inp.players:
            if p.player_id not in record['reference']:
                continue
            s = sim[p.player_id]
            if not np.isclose(sum(s[k] for k in POINT_COMPONENTS), s['xPts'], atol=1e-10, rtol=0):
                raise ValueError('Point components do not sum')
            rows.append(dict(fixture_uuid=record['core_fixture'], player_uuid=p.player_id,
                             gw=record['origin'], mode=mode, pos=p.position, xp=s['xPts'],
                             goal_mu=s['goal_mean'], assist_mu=s['assist_mean'],
                             p_goal=s['p_goal'], p_assist=s['p_assist'], bps_mean=s['bps_mean'],
                             sim_minutes=s['expected_minutes'], finishing_factor=gf[p.player_id],
                             historical_xg=record['historical_xg'][p.player_id],
                             **{k:s[k] for k in POINT_COMPONENTS},
                             **{k:s[k] for k in ('p_bonus_1','p_bonus_2','p_bonus_3')}))
    write_records(path, [dict(signature=signature, rows=rows)])
    return rows


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--db', default='work/core.sqlite3')
    parser.add_argument('--original-root', required=True)
    parser.add_argument('--mm-root', required=True)
    parser.add_argument('--out', default='analysis/results/general-conversion-20261020')
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--draws', type=int, default=400)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    obs, _, _, audit = observations(args.db)
    cuts = deadlines(Path(args.mm_root))
    fingerprint = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
        'scripts/replay_general_conversion.py', 'scripts/replay_pm_conversion.py',
        'scripts/research_pm_conversion.py', 'src/fpl_v1_1_model/experimental_receiver_conversion.py',
        'src/fpl_v1_1_model/experimental_player_pm.py', 'src/fpl_v1_1_model/joint_simulator.py')}
    for season in ('2024-25', '2025-26'):
        matches = list(Path(args.original_root).rglob(f'mm-pm-{season}/inputs.jsonl.gz'))
        if len(matches) != 1:
            raise ValueError('Missing/ambiguous original capture')
        records = target_records(matches[0], args.db, season)
        if season == '2024-25':
            records = [r for r in records if r['origin'] >= 22]
        if args.limit:
            records = records[:args.limit]
        states = {}
        prepared = []
        for r in records:
            cut = cuts[season][r['origin']]
            state = states.setdefault(r['origin'], None)
            if state is None:
                state = weighted_states(obs, cut, season, None)
                states[r['origin']] = state
            inp = decode(copy.deepcopy(r['input']))
            gf, _ = factors(inp, state, tau=20.)
            if pd.Timestamp(state[-1]) >= cut:
                raise ValueError('Future conversion observations')
            r = dict(r)
            r.pop('candidate_inputs', None)
            r.update(cutoff=str(cut), factors=gf,
                     historical_xg={p.player_id: float(state[0].loc[p.player_id, 'xg'])
                                    if p.player_id in state[0].index else 0. for p in inp.players})
            prepared.append(r)
        write_records(out / f'{season}_prepared.jsonl.gz', prepared)
        cache = out / f'cache_{season}'
        cache.mkdir(exist_ok=True)
        rows = []
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            tasks = [pool.submit(evaluate, (r, str(cache), fingerprint, args.draws)) for r in prepared]
            for i, future in enumerate(as_completed(tasks)):
                rows.extend(future.result())
                if (i + 1) % 10 == 0 or i + 1 == len(tasks):
                    print(season, i + 1, '/', len(tasks), 'fixtures complete', flush=True)
        truth = obs[obs.season.eq(season)][['fixture_uuid','player_uuid','goals','fpl_assists',
                                          'total_points','minutes','bonus','bps']]
        frame = pd.DataFrame(rows).merge(truth, on=['fixture_uuid','player_uuid'],
                                        validate='many_to_one', how='left')
        if frame[['goals','fpl_assists','total_points','minutes','bonus','bps']].isna().any().any():
            raise ValueError('Missing target truth; no zero filling')
        frame = frame.sort_values(['fixture_uuid','player_uuid','mode']).reset_index(drop=True)
        write_frame(out / f'{season}_predictions.csv.gz', frame)
        result = summarize(frame)
        # Labels come only from pre-match history, never target finishing outcomes.
        groups = {}
        for label, mask in (
            ('weak_history_xg_lt5', frame.historical_xg.lt(5)),
            ('factor_above1.05', frame.finishing_factor.gt(1.05)),
            ('factor_below0.95', frame.finishing_factor.lt(.95)),
            ('factor_near1', frame.finishing_factor.between(.95, 1.05)),
        ):
            if mask.any():
                groups[label] = summarize(frame[mask])
        report = dict(classification='OFFLINE_ORIGINAL_PM_FINISHER_RECEIVER_ABLATION',
                      season=season, fixtures=len(prepared), draws=args.draws,
                      original_exact=args.draws == 400, results=result, groups=groups,
                      source_sha256=hashlib.sha256(matches[0].read_bytes()).hexdigest(),
                      source_audit=audit, fingerprint=fingerprint,
                      limitations=['Previously used historical periods, not pristine holdouts',
                                   'All-xG includes penalties; no isolated NPG finishing claim',
                                   'Goal weight approximates receiver chance share; no creator links',
                                   'Original independent minute sampler held identical across arms',
                                   'Paired bootstrap omits some Monte Carlo uncertainty',
                                   'Poisson count NLL is an approximation; binary scores use MC smoothing',
                                   'No actual B-MM interaction or six-GW TS promotion test'],
                      production_changed=False, promotion_allowed=False)
        (out / f'{season}_report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
        print(json.dumps({'season': season, 'fixtures': len(prepared), 'metrics': {
            mode: {k: result['metrics'][mode][k] for k in ('mae','rmse','bias')}
            for mode in MODES}}, indent=2), flush=True)


if __name__ == '__main__':
    main()
