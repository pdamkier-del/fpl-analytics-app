"""Immutable first-attempt harness; preregister before execution."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import signal
import sys
import time
import traceback

START = time.perf_counter()
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'research/ts_search/code'))
from run_experiment import load_frozen, forecast, write, digest
from reference import legal_squads, legal_nomination, scalar_score, transition, exact_path
from candidate import funding_pairs
from generate import cases
import numpy as np


def evaluate(case, modules, development):
    planner, season, scoring, live, config, _ = modules
    players = {p['id']: p for p in case['players']}
    squads = legal_squads(players)
    f = forecast(case)
    meta, origin = live.project(f)
    initial = season.ReplayState(
        {p: season.OwnedPlayer(p, players[p]['purchase']) for p in case['initial_ids']},
        case['bank'], case['free_transfers'])
    original_state = asdict(initial)
    row = dict(id=case['id'], family=case['family'], status='running', errors=[],
               legal_squads=len(squads), audits=0, arms={})
    tables = [{} for _ in range(6)]
    with scoring.preview_scoring(f) as scorer:
        for g in range(6):
            for ids in squads:
                nom = scorer.decision(g+1, ids)
                positions = tuple(players[p]['position'] for p in ids)
                points = np.array([players[p]['points'][g] for p in ids]).T
                minutes = np.array([players[p]['minutes'][g] for p in ids]).T
                independent = scalar_score(ids, positions, points, minutes, nom[:4])
                row['audits'] += 1
                if not legal_nomination(ids, positions, nom[:4]):
                    row['errors'].append(dict(kind='illegal_nomination', gw=g+1, ids=ids))
                if abs(independent - nom[-1]) > 1e-9:
                    row['errors'].append(dict(kind='scorer', gw=g+1, ids=ids))
                tables[g][ids] = nom[-1]
        for arm in (['candidate'] if development else ['baseline', 'candidate']):
            before = planner._fast_local_candidate_squads
            t = time.perf_counter()
            if arm == 'candidate':
                with funding_pairs(planner):
                    result = planner.plan_transfer_path(initial, meta, origin, 1, config)
            else:
                result = planner.plan_transfer_path(initial, meta, origin, 1, config)
            elapsed = time.perf_counter() - t
            assert before is planner._fast_local_candidate_squads
            assert original_state == asdict(initial)
            value = 0.
            purchases = tuple(sorted((p, players[p]['purchase']) for p in case['initial_ids']))
            bank, ft = case['bank'], case['free_transfers']
            assert len(result.path) == 6
            for g, action in enumerate(result.path):
                selected = tuple(sorted((set(dict(purchases))-set(action.outgoing)) | set(action.incoming)))
                if selected not in tables[g] or action.transfers > 2:
                    row['errors'].append(dict(kind='illegal_transfer', arm=arm, gw=g+1))
                    break
                move = transition(purchases, bank, ft, selected, players)
                if move is None:
                    row['errors'].append(dict(kind='unaffordable', arm=arm, gw=g+1))
                    break
                after, outgoing, incoming, hits, paid = move
                expected = dict(outgoing=outgoing, incoming=incoming, bank_before=bank,
                                bank_after=after[1], free_transfers_before=ft,
                                free_transfers_after=after[2], official_hit_points=hits,
                                uncertainty_penalty=paid*config.hit_uncertainty_buffer)
                for k, v in expected.items():
                    if getattr(action, k) != v:
                        row['errors'].append(dict(kind='state_accounting', arm=arm, gw=g+1, field=k))
                score = tables[g][selected]
                if max(abs(action.projected_manager_score-score),
                       abs(action.utility_this_gw-(score-hits-paid*config.hit_uncertainty_buffer))) > 1e-9:
                    row['errors'].append(dict(kind='path_scoring', arm=arm, gw=g+1))
                value += config.weights[g]*score-hits-paid*config.hit_uncertainty_buffer
                purchases, bank, ft = after
            if abs(value-result.objective) > 1e-9:
                row['errors'].append(dict(kind='objective', arm=arm))
            row['arms'][arm] = dict(seconds=elapsed, objective=result.objective,
                                    replayed_objective=value, path=asdict(result)['path'])
    if development:
        archive = development[case['id']]
        row['arms']['baseline'] = dict(objective=archive['heuristic']['objective'],
                                       source='PR48 archived; not rerun', seconds=None)
        row['exact'] = dict(objective=archive['fixed_nomination_exact']['objective'],
                            source='PR48 archived fixed-nomination reference; not rerun')
    else:
        t = time.perf_counter()
        row['exact'] = exact_path(case, players, squads, tables, config.weights,
                                  config.hit_uncertainty_buffer)
        row['reference_seconds'] = time.perf_counter()-t
    for arm, data in row['arms'].items():
        data['gap'] = row['exact']['objective']-data['objective']
        if data['gap'] < -1e-9:
            row['errors'].append(dict(kind='reference_violation', arm=arm))
    row['improvement'] = row['arms']['baseline']['gap']-row['arms']['candidate']['gap']
    row['status'] = 'failed_gate' if row['errors'] else 'completed'
    scoring.ScenarioScorer.decision.cache_clear()
    return row


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--frozen-root', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--phase', choices=['development', 'holdout'], required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    assert not any(a.out.iterdir()), 'Never overwrite an attempted run'
    sys.path.insert(0, str(ROOT/'research/tools'))
    import registry
    entry = registry.read()['EXP-TS-FUNDING-001']
    assert entry['state'] == 'running'
    assert entry['implementation']['harness_sha256'] == digest(__file__)
    manifest = json.loads((HERE/'implementation-manifest.json').read_text())
    for path, h in manifest['files'].items():
        assert digest(ROOT/path) == h, path
    result = dict(phase=a.phase, status='running', rows=[], not_run=[],
                  protocol_sha256=entry['sha256'], manifest=manifest,
                  command=sys.argv, python=sys.version, numpy=np.__version__)
    budget = 120 if a.phase == 'development' else 240
    def timeout(*_):
        raise TimeoutError('Preregistered phase/per-case wall budget exhausted')
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(.001, budget-(time.perf_counter()-START)))
    pending = []
    try:
        modules = load_frozen(a.frozen_root)
        result['configuration'] = asdict(modules[4])
        development = None
        if a.phase == 'development':
            pending = json.loads((ROOT/'research/ts_search/inputs/instances.json').read_text())['cases']
            archive = json.loads((ROOT/'research/results/EXP-TS-SEARCH-001/initial-run/results.json').read_text())
            development = {r['id']: r for r in archive['rows']}
        else:
            pending = cases()
            write(a.out/'instances.json', dict(cases=pending))
            result['instances_sha256'] = digest(a.out/'instances.json')
        for case in pending:
            remaining = budget-(time.perf_counter()-START)
            if remaining <= 0:
                raise TimeoutError('Phase budget exhausted')
            signal.setitimer(signal.ITIMER_REAL, min(10, remaining) if a.phase == 'holdout' else remaining)
            t = time.perf_counter()
            try:
                row = evaluate(case, modules, development)
            except Exception as e:
                row = dict(id=case['id'], family=case['family'], status='error',
                           error=repr(e), traceback=traceback.format_exc())
            row['elapsed_seconds'] = time.perf_counter()-t
            result['rows'].append(row)
            print(case['id'], row['status'], round(row['elapsed_seconds'], 4), flush=True)
            write(a.out/'results.json', result)
            if time.perf_counter()-START >= budget:
                raise TimeoutError('Phase budget exhausted')
        result['status'] = 'completed' if all(r['status']=='completed' for r in result['rows']) else 'failed_gate'
    except Exception as e:
        result['status'] = 'blocked_execution'
        result['error'] = repr(e)
        result['traceback'] = traceback.format_exc()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        done = {r['id'] for r in result['rows']}
        result['not_run'] = [c['id'] for c in pending if c['id'] not in done]
        result['elapsed_seconds'] = time.perf_counter()-START
        write(a.out/'results.json', result)
    print(result['status'], result['elapsed_seconds'], flush=True)


if __name__ == '__main__':
    main()
