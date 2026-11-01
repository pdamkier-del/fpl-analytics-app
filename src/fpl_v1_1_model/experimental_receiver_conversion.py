"""Offline isolated active-finisher conversion, using the existing PM adapter."""
from contextlib import contextmanager
import numpy as np
from . import experimental_player_pm as player_pm


def receiver_rates(inp, spec, exposure):
    result = {}
    for team, lam, pen, conv in (
        (inp.home_team, inp.lambda_home_goals, inp.lambda_home_penalties, inp.home_penalty_conversion),
        (inp.away_team, inp.lambda_away_goals, inp.lambda_away_penalties, inp.away_penalty_conversion),
    ):
        ps = [p for p in inp.players if p.team == team]
        weights = np.array([spec['base_weights'][p.player_id] for p in ps])[:, None]
        theta = np.array([spec['factors'][p.player_id] for p in ps])[:, None]
        e = np.array([np.broadcast_to(exposure[p.player_id], (90,)) for p in ps])
        if not np.isfinite(weights).all() or not np.isfinite(theta).all() or not np.isfinite(e).all():
            raise ValueError('Non-finite receiver evidence')
        if (weights < 0).any() or (theta <= 0).any() or (e < 0).any() or (e > 1).any():
            raise ValueError('Invalid receiver evidence')
        chance = weights * e
        den = chance.sum(0)
        multiplier = np.divide((chance * theta).sum(0), den, out=np.ones(90), where=den > 0)
        ordinary = max(0., lam - pen * conv) * multiplier
        result[str(team)] = dict(xg=float(lam), ordinary=float(ordinary.mean()),
                                 total=float(ordinary.mean() + pen * conv), bins=ordinary.tolist(),
                                 active_exposure=float(e.mean(1).sum()))
    return result, {}


@contextmanager
def shadow_receiver_conversion(inp, factors):
    if set(factors) != {p.player_id for p in inp.players}:
        raise ValueError('Incomplete finishing factors')
    spec = dict(base_weights={p.player_id: p.goal_weight for p in inp.players}, factors=factors)
    original = player_pm.lineup_rates
    try:
        player_pm.lineup_rates = receiver_rates
        with player_pm.shadow_player_intensity(spec) as diagnostics:
            yield diagnostics
    finally:
        player_pm.lineup_rates = original
