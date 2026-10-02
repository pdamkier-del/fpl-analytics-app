"""Regression checks for repeated source fixture keys and quarantined history."""
import sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from audit_independent_cl_fixtures import normalize,parse_inventory


def test_inventory_aliases_and_penalty_score():
    assert normalize('Club Atlético de Madrid (ESP)')==normalize('atletico-madrid')
    text='▪ Final\nSat May 30 2026\n  21:00 Arsenal FC (ENG) v Paris Saint-Germain (FRA)  4-3 pen. 1-1 a.e.t.\n'
    r=parse_inventory(text).iloc[0]
    assert (r.home_score,r.away_score)==(1,1)
    assert r.kickoff_candidate=='2026-05-30T19:00:00+00:00'


def test_quarantined_keys_never_enter_workload_history():
    q=pd.read_csv(ROOT/'analysis/results/independent-cl-audit/workload_quarantine.csv')
    assert len(q)==20 and not q.match_id.duplicated().any()
    for name in ('official_player_minutes.csv','team_match_coverage.csv'):
        frame=pd.read_csv(ROOT/'analysis/results/workload-quality-v2'/name)
        assert not frame.match_id.isin(q.match_id).any()


def test_cup_quarantine_preserves_pl_only_forecast():
    path='reused_holdout_diagnostic_predictions.csv.gz'
    old=pd.read_csv(ROOT/'analysis/results/workload-minutes-v1'/path)
    new=pd.read_csv(ROOT/'analysis/results/workload-quality-minutes-v2'/path)
    cols=[c for c in old if 'pl_only' in c]
    assert len(cols)>=2
    pd.testing.assert_frame_equal(old[cols],new[cols],check_exact=True)


def test_known_temporal_conflicts_block_kickoff_recovery():
    import json
    summary=json.loads((ROOT/'analysis/results/independent-cl-audit/summary.json').read_text())
    assert summary['timestamp_anchor_mismatches']==3
    assert not summary['recovery_gate_passed'] and summary['accepted_overrides']==0
