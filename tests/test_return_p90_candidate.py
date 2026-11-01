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
