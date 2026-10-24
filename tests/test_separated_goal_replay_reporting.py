"""Exercise the replay CLI's final reporting after task preparation is isolated."""
import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd


def test_approved_nonpenalty_policy_matches_current_repository_sources():
    from nonpenalty_goal_bridge import load
    root=Path(__file__).resolve().parents[1]
    model,policy=load(root,root/'analysis/results/nonpenalty-goal-head-20261023/policy.json')
    assert policy['approved']is True
    assert set(model['allocation']['columns'])=={'np_last_xg','np_recent3_xg'}


def test_cli_reports_penalty_taker_cohort_after_preparation(monkeypatch, tmp_path):
    analysis = Path(__file__).resolve().parents[1] / 'analysis'
    monkeypatch.syspath_prepend(str(analysis))
    spec = importlib.util.spec_from_file_location('separated_replay_reporting', analysis/'test_separated_goal_head.py')
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    monkeypatch.setattr(replay, 'ROOT', tmp_path)
    actuals, simulated, reference, attempts = [], [], [], []
    for season in ['2024-25', '2025-26']:
        for player, points in [('taker', 2.), ('other', 1.)]:
            keys = dict(season=season, fixture_uuid=season+'-fixture', player_uuid=player)
            actuals.append(dict(**keys, minutes=90, total_points=points))
            reference.append(dict(**keys, arm='candidate', xp=points))
            for arm in ['baseline', 'candidate']:
                simulated.append(dict(**keys, arm=arm, xp=points+(0.001 if arm=='candidate' else 0)))
        attempts.append(dict(season=season, player_uuid='taker'))
    for relative, rows in [
        ('analysis/results/penalty-neutral-sources-20261023/verified-attempts.csv', attempts),
        ('analysis/results/joint-role-candidate-20261022/pm-predictions.csv.gz', reference)]:
        path = tmp_path/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(path, index=False)
    monkeypatch.setattr(replay, 'prepare_tasks', lambda fitted, out: ([None], pd.DataFrame(actuals)))
    monkeypatch.setattr(replay, 'evaluate', lambda task: simulated)
    monkeypatch.setattr(replay, 'ProcessPoolExecutor', ThreadPoolExecutor)
    model = tmp_path/'model.json'
    model.write_text('{}')
    out = tmp_path/'output'
    monkeypatch.setattr(sys, 'argv', ['replay', '--out', str(out), '--model', str(model), '--workers', '1'])
    replay.main()
    decision = json.loads((out/'decision.json').read_text())
    assert decision['passed'] is True
    assert decision['baseline_max_xp_error'] == 0
    takers = [row for row in decision['metrics'] if row['cohort']=='takers']
    assert len(takers) == 4
    assert all(row['rows']==1 for row in takers)
    assert len(decision['metrics']) == 12
