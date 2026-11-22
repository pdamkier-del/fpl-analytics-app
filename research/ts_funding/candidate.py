"""Research-only supplementary funding pairs. No production imports at import time."""
from contextlib import contextmanager


def propose(planner, original, state, meta, origin, gws, weights, max_transfers,
            top_targets_per_position, local_bundle_beam, candidate_return_per_depth,
            prepared=None):
    args = (state, meta, origin, gws, weights, max_transfers,
            top_targets_per_position, local_bundle_beam, candidate_return_per_depth)
    baseline = original(*args, prepared=prepared)
    if max_transfers < 2:
        return baseline
    if prepared is None:
        prepared = planner._prepare_local_candidates(
            meta, origin, gws, weights, top_targets_per_position)
    rows, values, targets = prepared
    owned = set(state.squad)
    legs = []
    for outgoing in sorted(owned):
        position, _, price = rows[outgoing]
        sale = planner.selling_price(state.squad[outgoing].purchase_price, price)
        for incoming in targets.get(position, []):
            if incoming not in owned:
                legs.append((outgoing, incoming, sale - rows[incoming][2],
                             float(values.get(incoming, 0) - values.get(outgoing, 0))))
    extras = {}
    for a in legs:
        # A strictly negative, cash-releasing leg; the upgrade needs its funding.
        if not (a[2] > 0 and a[3] < -1e-12):
            continue
        for b in legs:
            if (a[0] == b[0] or a[1] == b[1] or b[3] <= 0
                    or state.bank + b[2] >= 0
                    or state.bank + a[2] + b[2] < 0
                    or a[3] + b[3] <= 1e-12):
                continue
            selected = (owned - {a[0], b[0]}) | {a[1], b[1]}
            if not planner.valid_squad(meta, selected):
                continue
            after, _, _ = planner._apply_selected_squad(state, selected, meta)
            key = tuple(sorted(selected))
            extras[key] = (a[3] + b[3], after.bank)
    seen = {tuple(sorted(s)) for s in baseline}
    ranked = sorted(extras, key=lambda k: (-extras[k][0], -extras[k][1], k))
    supplemental = [k for k in ranked if k not in seen][:max(1, int(candidate_return_per_depth))]
    return [*baseline, *(set(k) for k in supplemental)]


@contextmanager
def funding_pairs(planner):
    """Single-process test adapter; always restore the frozen proposer."""
    original = planner._fast_local_candidate_squads
    def wrapped(*args, **kwargs):
        return propose(planner, original, *args, **kwargs)
    planner._fast_local_candidate_squads = wrapped
    try:
        yield
    finally:
        planner._fast_local_candidate_squads = original
