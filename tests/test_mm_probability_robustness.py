import numpy as np
import pandas as pd
import pytest

from validate_mm_probability_robustness import probability_scores, block_delta, paired_rows


def sample():
    return pd.DataFrame([dict(season='2024-25', fixture_uuid=f'f{i}', player_uuid='p',
        gw=i+22, cutoff=f'2025-01-{i+1:02d}T12:00Z', team_id=1, y=i % 2,
        minutes=90*(i % 2), p=.5, q=.2, x=46.) for i in range(8)])


def test_reliability_bins_include_endpoints_and_reconcile_counts():
    r = probability_scores([0., .25, .75, 1.], [0, 0, 1, 1])
    assert sum(x['rows'] for x in r['reliability']) == 4
    assert r['reliability'][-1]['bin'] == 9
    assert r['brier'] == pytest.approx(.03125)
    assert r['endpoint_contradictions'] == 0
    assert probability_scores([0., 1.], [1, 0])['endpoint_contradictions'] == 2


@pytest.mark.parametrize('p,y', [([1.1], [1]), ([-.1], [0]), ([np.nan], [0]),
                                ([.5], [.5]), ([.5, .6], [0]), ([], [])])
def test_illegal_or_missing_probabilities_fail_closed(p, y):
    with pytest.raises(ValueError):
        probability_scores(p, y)


def test_identical_arms_reproduce_zero_deltas_for_temporal_blocks():
    f = sample()
    for length in [1, 2, 4]:
        a = block_delta(f, f.sample(frac=1, random_state=1), length, draws=50)
        b = block_delta(f, f, length, draws=50)
        assert a == b
        for v in a['metrics'].values():
            assert v['delta'] == 0
            assert v['interval95'] == [0., 0.]


def test_paired_audit_rejects_changed_truth_deadline_and_duplicate_identity():
    f = sample()
    for field, value in [('minutes', 25), ('cutoff', '2025-01-01T13:00Z'), ('gw', 99)]:
        bad = f.copy()
        bad.loc[0, field] = value
        with pytest.raises(ValueError):
            paired_rows(bad, f)
    with pytest.raises(ValueError):
        paired_rows(pd.concat([f, f.iloc[:1]]), pd.concat([f, f.iloc[:1]]))


def test_no_cross_season_bootstrap_or_silent_missing_gameweek():
    f = sample()
    mixed = f.copy()
    mixed.loc[0, 'season'] = '2025-26'
    with pytest.raises(ValueError):
        paired_rows(mixed, mixed)
    gap = f[f.gw.ne(25)]
    with pytest.raises(ValueError):
        block_delta(gap, gap)
