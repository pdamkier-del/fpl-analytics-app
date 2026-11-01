from dataclasses import replace
import copy
import numpy as np
import pytest
from test_physical_timeline import fixture
from fpl_v1_1_model.experimental_physical_timeline import PhysicalKernel, validate_timeline
from precision_audit.return_p90 import ReturnP90Kernel


def regular_fixture():
    inp = fixture()
    return replace(inp, players=tuple(
        p if p.is_keeper or 'unavailable' in p.player_id else replace(
            p, p_start=.95 if int(p.player_id[1:]) < 10 else .05,
            start_minutes_mean=70 if p.player_id == 'H00' else 90 if int(p.player_id[1:]) < 10 else 72)
        for p in inp.players))


def test_disabled_candidate_exact_ensemble_and_same_seed_identity():
    inp = regular_fixture()
    a = PhysicalKernel(inp)
    b = ReturnP90Kernel(inp, returning=['H00'], return_scale=1, regular_floor=0)
    for pid in a.moments:
        assert a.moments[pid]['pmf'] == b.moments[pid]['pmf']
    ra, rb = np.random.default_rng(23), np.random.default_rng(23)
    for _ in range(100):
        assert a.sample(ra) == b.sample(rb)


def test_candidate_targets_return_exit_and_regular_full_match_atom():
    inp = regular_fixture()
    a = PhysicalKernel(inp)
    b = ReturnP90Kernel(inp, returning=['H00'])
    assert b.moments['H00']['x'] > a.moments['H00']['x']
    assert sum(b.moments[p.player_id]['p90'] for p in inp.players
               if not p.is_keeper and p.p_start >= .9 and p.player_id != 'H00') < sum(
                   a.moments[p.player_id]['p90'] for p in inp.players
                   if not p.is_keeper and p.p_start >= .9 and p.player_id != 'H00')


def test_budget_availability_starts_and_probability_order_all_draws():
    inp = regular_fixture()
    b = ReturnP90Kernel(inp, returning=['H00'])
    before = copy.deepcopy(inp)
    for p in inp.players:
        if p.is_keeper:
            continue
        m = b.moments[p.player_id]
        assert m['p'] == pytest.approx(p.p_start, abs=1e-6)
        assert 0 <= m['p90'] <= m['p60'] <= m['p_play'] <= 1+1e-12
        assert m['p_play'] <= p.p_start+(1-p.p_start)*p.p_cameo_given_bench+2e-6
        assert m['p']*m['s']+(1-m['p'])*m['q']*m['c'] == pytest.approx(m['x'])
    for team in ['H', 'A']:
        assert sum(b.moments[p.player_id]['x'] for p in inp.players
                   if p.team == team and not p.is_keeper) == pytest.approx(900)
    rng = np.random.default_rng(31)
    for _ in range(500):
        t = b.sample(rng)
        assert validate_timeline(inp, t)
        assert t['Hunavailable'][0] == 0
    assert inp == before


def test_permutation_invariance():
    inp = regular_fixture()
    a = ReturnP90Kernel(inp, returning=['H00'])
    b = ReturnP90Kernel(replace(inp, players=tuple(reversed(inp.players))), returning=['H00'])
    assert a.moments == b.moments


@pytest.mark.parametrize('options', [dict(return_scale=0), dict(return_scale=np.nan),
    dict(regular_floor=-1), dict(regular_floor=11), dict(returning=['missing']),
    dict(returning=['HGK'])])
def test_invalid_candidate_fails_closed(options):
    with pytest.raises(ValueError):
        ReturnP90Kernel(regular_fixture(), **options)


def test_fpl_clock_labels_are_not_reconciled_to_physical_totals():
    import pandas as pd
    from precision_audit.evaluate_return_p90 import summaries
    f = pd.DataFrame([dict(season='test', arm='baseline', fixture_uuid='f',
        returning=True, regular=True, minutes=89., actual_minutes=90.,
        p=1., actual_start=1., p60=1., p90=.6)])
    m = summaries(f).iloc[0]
    assert m.minute_bias == -1
    assert m.p90_brier == pytest.approx(.16)


def test_application_does_not_import_candidate():
    from pathlib import Path
    for folder in ['app', 'src', 'scripts', 'service']:
        for p in Path(folder).rglob('*.py'):
            assert 'precision_audit.return_p90' not in p.read_text()


def test_return_start_repair_keeps_legal_xi_and_availability_ceiling():
    from precision_audit.return_p90 import tilt_return_starts
    inp = regular_fixture()
    modified, dist = tilt_return_starts(inp, {}, ['H00'])
    old = {p.player_id: p for p in inp.players}
    new = {p.player_id: p for p in modified.players}
    assert new['H00'].p_start > old['H00'].p_start
    for team in ['H', 'A']:
        field = [p for p in modified.players if p.team == team and not p.is_keeper]
        assert sum(p.p_start for p in field) == pytest.approx(10)
        assert all(len(r.players) == len(set(r.players)) == 10 for r in dist[team])
    for pid, p in new.items():
        before = old[pid]
        assert p.p_start+(1-p.p_start)*p.p_cameo_given_bench == pytest.approx(
            before.p_start+(1-before.p_start)*before.p_cameo_given_bench)
        assert p.p_start <= before.p_start+(1-before.p_start)*before.p_cameo_given_bench+1e-10
        if p.is_keeper:
            assert p == before
    kernel = PhysicalKernel(modified, dist)
    rng = np.random.default_rng(912)
    for _ in range(100):
        assert validate_timeline(inp, kernel.sample(rng))


def test_return_tilt_disabled_exact_identity():
    from precision_audit.return_p90 import tilt_return_starts
    inp = regular_fixture()
    assert tilt_return_starts(inp, {}, ['H00'], log_odds=0) == (inp, {})
    assert tilt_return_starts(inp, {}, []) == (inp, {})


def test_medical_and_suspension_episodes_are_separate_and_future_features_rejected(tmp_path):
    import pandas as pd
    from precision_audit.evaluate_return_p90 import annotate_return_kinds
    p = tmp_path/'features.csv'
    f = pd.DataFrame([dict(season='s', fixture_uuid='f', player_uuid=pid,
        cutoff='2026-01-01T00:00:00Z', return_active=True, return_kind=kind,
        max_history_known_at='2025-12-31T00:00:00Z') for pid, kind in
        [('injury', 'medical_selection'), ('suspended', 'suspension_selection')]])
    f.to_csv(p, index=False)
    r = [dict(season='s', fixture_uuid='f', cutoff='2026-01-01T00:00:00Z',
        meta={pid: dict(return_active=True) for pid in ['injury', 'suspended']})]
    annotate_return_kinds(r, p)
    assert r[0]['meta']['injury']['return_kind'] == 'medical_selection'
    assert r[0]['meta']['suspended']['return_kind'] == 'suspension_selection'
    f.loc[0, 'max_history_known_at'] = f.loc[0, 'cutoff']
    f.to_csv(p, index=False)
    with pytest.raises(ValueError, match='Future'):
        annotate_return_kinds(r, p)


def test_baseline_reuse_is_exact_and_does_not_mutate_shared_ensembles():
    from precision_audit.return_p90 import tilt_return_starts
    inp = regular_fixture()
    baseline = PhysicalKernel(inp)
    saved = copy.deepcopy(baseline.moments)
    for scale, floor in [(1, 0), (.5, 0), (1, 2), (.5, 2), (1, .5)]:
        expected = ReturnP90Kernel(inp, returning=['H00'], return_scale=scale, regular_floor=floor)
        cached = ReturnP90Kernel(inp, returning=['H00'], return_scale=scale,
                                 regular_floor=floor, baseline=baseline)
        assert expected.moments == cached.moments
        r1, r2 = np.random.default_rng(45), np.random.default_rng(45)
        for _ in range(50):
            assert expected.sample(r1) == cached.sample(r2)
    assert baseline.moments == saved
    a, da = tilt_return_starts(inp, {}, ['H00'])
    b, db = tilt_return_starts(inp, {}, ['H00'], baseline=baseline)
    assert (a, da) == (b, db)


def test_baseline_reuse_rejects_wrong_input_or_state_count():
    inp = regular_fixture()
    with pytest.raises(ValueError, match='contract'):
        ReturnP90Kernel(inp, baseline=PhysicalKernel(inp, states=64))
    with pytest.raises(ValueError, match='contract'):
        ReturnP90Kernel(inp, baseline=PhysicalKernel(fixture()))
