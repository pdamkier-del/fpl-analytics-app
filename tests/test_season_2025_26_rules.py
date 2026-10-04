import pytest
from fpl_xpts.season_2025_26_rules import apply_transfers, chip_is_available, free_transfers_for_deadline


def test_afcon_is_topup_and_does_not_repeat_in_gw17():
    for bank in range(1, 6):
        assert free_transfers_for_deadline(16, bank) == 5
    result = apply_transfers(16, 2, 3)
    assert (result.available_free_transfers, result.hit_points, result.next_ordinary_balance) == (5, 0, 3)
    assert free_transfers_for_deadline(17, result.next_ordinary_balance) == 3


def test_roll_hit_and_cap_bookkeeping():
    assert apply_transfers(12, 4, 0).next_ordinary_balance == 5
    assert apply_transfers(12, 5, 0).next_ordinary_balance == 5
    result = apply_transfers(12, 2, 4)
    assert (result.hit_points, result.next_ordinary_balance) == (8, 1)


def test_wc_and_fh_preserve_bank_without_extra_accrual():
    for chip in ('wildcard', 'free_hit'):
        result = apply_transfers(12, 3, 15, chip)
        assert (result.hit_points, result.next_ordinary_balance) == (0, 3)
        gw15 = apply_transfers(15, 2, 15, chip)
        assert free_transfers_for_deadline(16, gw15.next_ordinary_balance) == 5
        assert apply_transfers(16, 1, 15, chip).next_ordinary_balance == 5


def test_initial_squad_and_final_deadline():
    assert apply_transfers(1, 0, 15, 'bench_boost').hit_points == 0
    assert apply_transfers(1, 0, 15).next_ordinary_balance == 1
    assert apply_transfers(38, 1, 2).next_ordinary_balance is None


def test_two_chip_sets_and_no_carry_of_unused_first_set():
    assert chip_is_available(19, 'bench_boost', {})
    assert not chip_is_available(19, 'bench_boost', {'bench_boost': [10]})
    assert chip_is_available(20, 'bench_boost', {'bench_boost': [10]})
    assert not chip_is_available(38, 'bench_boost', {'bench_boost': [10, 25]})


def test_opening_and_free_hit_boundary():
    assert chip_is_available(1, 'bench_boost', {})
    assert chip_is_available(1, 'triple_captain', {})
    assert not chip_is_available(1, 'free_hit', {})
    assert not chip_is_available(1, 'wildcard', {})
    assert not chip_is_available(20, 'free_hit', {'free_hit': [19]})
    assert chip_is_available(21, 'free_hit', {'free_hit': [19]})


def test_history_rejects_illegal_double_chip_and_future_information():
    for history in [{'bench_boost': [12], 'triple_captain': [12]}, {'wildcard': [3, 8]},
                    {'free_hit': [19, 20]}, {'bench_boost': [35]}, {'assistant_manager': [10]}]:
        with pytest.raises(ValueError):
            chip_is_available(30, 'wildcard', history)


def test_invalid_state_is_not_silently_coerced():
    for gw, bank, transfers, chip in [(0, 1, 0, None), (39, 1, 0, None), (12, 6, 0, None),
                                    (12, 1, -1, None), (12, 1, 1.5, None), (True, 1, 0, None),
                                    (12, 0, 0, None), (1, 0, 3, 'wildcard'), (12, 1, 1, 'assistant_manager')]:
        with pytest.raises(ValueError):
            apply_transfers(gw, bank, transfers, chip)
