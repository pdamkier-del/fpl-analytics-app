#!/usr/bin/env python3
"""Read-only temporal analysis and official transfer-accounting audit."""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis/results/ts-v3-weight-buffer-grid-20261005-v1'


def analyze():
    ranking = pd.read_csv(OUT / 'ranking.csv')
    violations = []
    for row in ranking.itertuples():
        log = pd.read_csv(OUT / row.label / 'tsv3_gameweek_log.csv')
        legal_ft = 0
        for gw in log.itertuples():
            count = int(gw.transfers)
            expected_hit = 4 * max(0, count - legal_ft)
            expected_ft = min(5, max(0, legal_ft - count) + 1)
            if int(gw.hit_cost) != expected_hit or int(gw.free_transfers_after) != expected_ft or count > 5:
                violations.append(dict(label=row.label, gw=int(gw.gw),
                    total_transfers=count, forced_transfers=int(gw.forced_transfers),
                    legal_ft_before=legal_ft, expected_hit_points=expected_hit,
                    recorded_hit_points=int(gw.hit_cost), expected_ft_after=expected_ft,
                    recorded_ft_after=int(gw.free_transfers_after)))
            legal_ft = expected_ft
    bad = {v['label'] for v in violations}
    ranking['official_transfer_accounting_valid'] = ~ranking.label.isin(bad)
    ranking.to_csv(OUT / 'ranking_audited.csv', index=False)
    pd.DataFrame(violations, columns=['label', 'gw', 'total_transfers', 'forced_transfers',
        'legal_ft_before', 'expected_hit_points', 'recorded_hit_points',
        'expected_ft_after', 'recorded_ft_after']).to_csv(OUT / 'transfer_accounting_violations.csv', index=False)
    valid = ranking[ranking.official_transfer_accounting_valid].copy()
    valid['rank_dev_valid'] = valid.points_gw1_21.rank(method='min', ascending=False).astype(int)
    valid['rank_late_valid'] = valid.points_gw22_38.rank(method='min', ascending=False).astype(int)
    valid['rank_season_valid'] = valid.total_points.rank(method='min', ascending=False).astype(int)
    valid.to_csv(OUT / 'ranking_valid.csv', index=False)
    for group, filename in [('buffer', 'mean_by_buffer_valid.csv'), ('name', 'mean_by_weighting_valid.csv'),
                            ('family', 'mean_by_family_valid.csv')]:
        valid.groupby(group).agg(count=('label', 'size'), mean_points=('total_points', 'mean'),
            mean_dev=('points_gw1_21', 'mean'), mean_late=('points_gw22_38', 'mean'),
            mean_transfers=('transfers', 'mean'), mean_hit_points=('hit_points', 'mean'),
            min_points=('total_points', 'min'), max_points=('total_points', 'max')).reset_index().to_csv(OUT / filename, index=False)
    summary = json.loads((OUT / 'summary.json').read_text())
    dev = valid.sort_values(['points_gw1_21', 'hits_gw1_21', 'transfers_gw1_21', 'label'], ascending=[False, True, True, True])
    late = valid.sort_values(['points_gw22_38', 'hits_gw22_38', 'transfers_gw22_38', 'label'], ascending=[False, True, True, True])
    season = valid.sort_values(['total_points', 'hit_points', 'transfers', 'label'], ascending=[False, True, True, True])
    robust = valid[(valid.delta_dev_vs_v3 > 0) & (valid.delta_late_vs_v3 > 0)]
    robust = robust.sort_values(['worst_period_gain_per_gw', 'total_points'], ascending=[False, False])
    def record(row):
        return {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in row.to_dict().items()}
    analysis = dict(completed=len(ranking), valid_count=len(valid),
        invalid_combinations=sorted(bad), accounting_violations=violations,
        predeclared_raw_dev_choice=summary['development_choice']['label'],
        raw_dev_choice_valid=summary['development_choice']['label'] not in bad,
        best_valid_dev_choice=record(dev.iloc[0]),
        valid_late_optimum=record(late.iloc[0]), valid_hindsight_season_max=record(season.iloc[0]),
        valid_optimum_switches=dev.iloc[0].label != late.iloc[0].label,
        valid_dev_max_labels=dev[dev.points_gw1_21 == dev.points_gw1_21.max()].label.tolist(),
        valid_late_max_labels=late[late.points_gw22_38 == late.points_gw22_38.max()].label.tolist(),
        valid_dev_and_late_maxima_overlap=bool(set(dev[dev.points_gw1_21 == dev.points_gw1_21.max()].label)
            & set(late[late.points_gw22_38 == late.points_gw22_38.max()].label)),
        robust_both_periods=[record(r) for _, r in robust.iterrows()],
        selection_note='Raw predeclared selection is preserved. Accounting-valid results are presented separately because the frozen engine has an existing forced-transfer FT/hit bug. Invalid paths are not corrected by subtracting hits: the cost could have changed decisions. No mechanics were changed.',
        averaging_note='Raw means retain all 36 requested combinations. Valid-only means can have unequal counts; also compare buffers on the common valid weighting set.')
    common = valid.groupby('name').buffer.nunique()
    common = common[common == 3].index.tolist()
    valid[valid.name.isin(common)].groupby('buffer').agg(count=('label', 'size'),
        mean_points=('total_points', 'mean'), mean_dev=('points_gw1_21', 'mean'),
        mean_late=('points_gw22_38', 'mean'),mean_transfers=('transfers','mean'),
        mean_hit_points=('hit_points','mean')).reset_index().to_csv(OUT / 'mean_by_buffer_common_valid.csv', index=False)
    analysis['common_valid_weightings'] = common
    (OUT / 'temporal_analysis.json').write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n')
    return analysis


if __name__ == '__main__':
    print(json.dumps(analyze(), indent=2, allow_nan=False))
