"""Opt-in 2025/26 bookkeeping rules, separate from transfer/chip strategy.

Not imported by the archived policy or simulator. For a manager entered before
GW1, call once with the balance before that deadline's transfers and the total
confirmed transfer count. This is not an incremental per-transfer API.
"""
from dataclasses import dataclass
from numbers import Integral
from typing import Mapping, Sequence

CHIPS = ('wildcard', 'free_hit', 'bench_boost', 'triple_captain')


def _integer(value, name, low, high=None):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < low or (high is not None and value > high):
        raise ValueError(f'Invalid {name}')
    return int(value)


def _gw(gw):
    return _integer(gw, 'gameweek', 1, 38)


def free_transfers_for_deadline(gw: int, ordinary_balance: int) -> int:
    """Top up to five for GW16; do not add five or reset subsequent GWs."""
    gw = _gw(gw)
    balance = _integer(ordinary_balance, 'free-transfer balance', 0, 5)
    if gw == 1:
        return 0  # Initial squad has unlimited transfers, not a finite FT bank.
    if balance == 0:
        raise ValueError('An established manager has at least one free transfer')
    return 5 if gw == 16 else balance


def chip_is_available(gw: int, chip: str, used: Mapping[str, Sequence[int]]) -> bool:
    """Legal chip availability; no strategic scoring or timing preferences."""
    gw = _gw(gw)
    if chip not in CHIPS or any(k not in CHIPS for k in used):
        raise ValueError('Unknown 2025/26 chip')
    weeks = []
    for name, history in used.items():
        halves = []
        for week in history:
            week = _gw(week)
            if week >= gw:
                raise ValueError('Chip history must precede the current deadline')
            if week == 1 and name in ('wildcard', 'free_hit'):
                raise ValueError('Illegal opening-gameweek chip history')
            halves.append(week <= 19)
            weeks.append(week)
        if len(set(halves)) != len(halves):
            raise ValueError('Chip used twice in the same half')
    if len(set(weeks)) != len(weeks):
        raise ValueError('More than one chip recorded in one gameweek')
    fh = sorted(used.get('free_hit', ()))
    if any(b == a + 1 for a, b in zip(fh, fh[1:])):
        raise ValueError('Consecutive Free Hits in recorded history')
    if gw == 1 and chip in ('wildcard', 'free_hit'):
        return False
    if any((week <= 19) == (gw <= 19) for week in used.get(chip, ())):
        return False
    return not (chip == 'free_hit' and gw - 1 in fh)


@dataclass(frozen=True)
class TransferTransition:
    available_free_transfers: int
    hit_points: int
    next_ordinary_balance: int | None


def apply_transfers(gw: int, ordinary_balance: int, transfer_count: int,
                    chip: str | None = None) -> TransferTransition:
    """Legal FT/hit bookkeeping only; chip history must be checked separately.

    WC/FH preserve the existing deadline balance rather than accrue another FT.
    AFCON is applied by free_transfers_for_deadline at the next GW16 boundary.
    GW1 has unlimited transfers; GW38 has no following decision deadline.
    """
    gw = _gw(gw)
    count = _integer(transfer_count, 'transfer count', 0)
    if chip is not None and chip not in CHIPS:
        raise ValueError('Unknown 2025/26 chip')
    if gw == 1 and chip in ('wildcard', 'free_hit'):
        raise ValueError('Wildcard/Free Hit unavailable for opening gameweek')
    available = free_transfers_for_deadline(gw, ordinary_balance)
    unlimited = gw == 1 or chip in ('wildcard', 'free_hit')
    hits = 0 if unlimited else 4 * max(0, count - available)
    if gw == 38:
        following = None
    elif gw == 1:
        following = 1
    elif chip in ('wildcard', 'free_hit'):
        following = available
    else:
        following = min(5, max(0, available - count) + 1)
    return TransferTransition(available, hits, following)
