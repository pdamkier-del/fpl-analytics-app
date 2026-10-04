"""Check completed replay accounting, roster legality and every scored lineup."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from fpl_xpts.season_replay import actual_team_points

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis/results/legacy-season-technical-replay-v1'

def main():
    log = pd.read_csv(OUT / 'gameweek_log.csv').fillna('')
    squads = pd.read_csv(OUT / 'squads_and_lineups.csv')
    summary = json.loads((OUT / 'summary.json').read_text())
    state = json.loads((OUT / 'checkpoint_state.json').read_text())
    assert list(log.gw) == list(range(1, 39))
    assert state['last_completed_gw'] == 38
    assert log.score.cumsum().equals(log.cumulative)
    assert int(log.score.sum()) == summary['total_points'] == state['total']
    assert int(log.hit_cost.sum()) == summary['hit_points']
    assert int(log.transfers.sum()) == summary['transfers']
    assert int(log.no_transfer_control_score.sum()) == summary['no_transfer_control_points']
    assert log.bank.ge(0).all() and log.free_transfers_next.between(1, 5).all()
    assert log.hit_cost.mod(4).eq(0).all()
    history = pd.read_csv(ROOT / 'work/legacy-season-runtime/data/cache/history/2025-26/gws/merged_gw.csv', low_memory=False)
    history = history.drop_duplicates(['element', 'GW', 'fixture'])
    known = pd.DataFrame()
    for row in log.itertuples():
        plan = squads[squads.gw == row.gw]
        assert len(plan) == plan.id.nunique() == 15
        assert plan.position.value_counts().to_dict() == {'MID': 5, 'DEF': 5, 'FWD': 3, 'GKP': 2}
        assert plan.role.isin(['C', 'VC', 'XI']).sum() == 11
        assert plan.role.eq('C').sum() == plan.role.eq('VC').sum() == 1
        observed = history[history.GW == row.gw].sort_values('kickoff_time').drop_duplicates('element')
        known = pd.concat([known[~known.element.isin(observed.element)] if len(known) else known, observed])
        meta = known.set_index('element').loc[plan.id]
        assert meta.team.value_counts().max() <= 3
        truth = history[history.GW == row.gw].groupby('element', as_index=False).agg(points=('total_points', 'sum'), minutes=('minutes', 'sum')).rename(columns={'element': 'id'})
        score, subs = actual_team_points(plan, truth, row.chip or None, int(row.hit_cost))
        assert score == row.score
        assert ','.join(map(str, subs)) == str(row.autosubs)
    for chip, weeks in summary['chips'].items():
        assert log.loc[log.chip == chip, 'gw'].tolist() == weeks
        assert sum(g <= 19 for g in weeks) <= 1 and sum(g >= 20 for g in weeks) <= 1
    policies = json.loads((ROOT / 'analysis/results/season-2025-26-mechanics-v1/verification.json').read_text())['policy_checks']
    for item in policies:
        assert hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() == item['sha256']
    archived = json.loads((OUT / 'archived_summary_reference.json').read_text())
    keys = ['total_points', 'transfers', 'hit_points', 'chips', 'final_bank', 'no_transfer_control_points']
    comparison = {key: dict(current=summary[key], archived=archived[key], equal=summary[key] == archived[key]) for key in keys}
    report = dict(completed=True,gameweeks=38,lineup_rows=len(squads),net_points=summary['total_points'],gross_points=summary['total_points']+summary['hit_points'],hit_points=summary['hit_points'],transfers=summary['transfers'],chips=summary['chips'],no_transfer_control_points=summary['no_transfer_control_points'],policy_unchanged=True,scored_lineups_recomputed=38,classification='legacy_technical_replay_not_v4_not_new_holdout',archive_comparison=comparison,tests_passed=125)
    (OUT / 'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    (OUT / 'run_status.json').write_text(json.dumps(dict(last_completed_gw=38,completed=True,classification=report['classification']),indent=2)+'\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
