from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from .optimize import POSITION_COUNTS, START_MAX, START_MIN
from .season_replay import ReplayState, selling_price, valid_squad
from .transfer_planner import (
    PlannerResult,
    TransferAction,
    next_free_transfers,
    projected_manager_score,
)


@dataclass(frozen=True)
class JointPlannerConfig:
    """Rolling 6GW transfer planner solved as one joint MILP.

    The point model is unchanged. Forecast manager points are horizon-weighted.
    Deterministic official hit costs and the hit uncertainty buffer are NOT
    horizon-discounted. Free-transfer value is endogenous through the exact
    FT transition state; there is no fixed saved-FT value.
    """

    weights: tuple[float, ...] = (1.00, 0.85, 0.70, 0.55, 0.40, 0.25)
    hit_uncertainty_buffer: float = 1.5
    max_transfers_per_week: int = 5
    first_gw_max_transfers: int | None = None
    time_limit: float = 60.0
    mip_rel_gap: float = 0.002


def _forecast_arrays(
    origin: pd.DataFrame,
    meta: pd.DataFrame,
    player_ids: list[int],
    gws: list[int],
) -> tuple[np.ndarray, np.ndarray]:
    """Return [H,N] xP and p(play) arrays using the frozen deadline forecast."""
    n = len(player_ids)
    h = len(gws)
    index = {pid: i for i, pid in enumerate(player_ids)}
    xp = np.zeros((h, n), dtype=float)
    pp = np.ones((h, n), dtype=float)

    cols = ["id", "gw", "xpts_mean"] + (["p_play"] if "p_play" in origin.columns else [])
    frame = origin[origin.gw.isin(gws)][cols].copy()
    agg = {"xpts_mean": "sum"}
    if "p_play" in frame.columns:
        agg["p_play"] = "max"
    frame = frame.groupby(["gw", "id"], as_index=False).agg(agg)

    gw_index = {int(gw): gi for gi, gw in enumerate(gws)}
    for row in frame.itertuples():
        pid = int(row.id)
        gw = int(row.gw)
        if pid not in index or gw not in gw_index:
            continue
        gi, i = gw_index[gw], index[pid]
        xp[gi, i] = float(row.xpts_mean)
        if hasattr(row, "p_play"):
            pp[gi, i] = min(1.0, max(0.0, float(row.p_play)))
    return xp, pp


def plan_transfer_path_joint(
    state: ReplayState,
    meta: pd.DataFrame,
    origin: pd.DataFrame,
    current_gw: int,
    config: JointPlannerConfig = JointPlannerConfig(),
) -> PlannerResult:
    """Solve the whole visible transfer/FT/squad/XI/captain path in one MILP.

    This removes the TS v3 candidate-generator bottleneck entirely:
    - every player in the current metadata table is eligible;
    - 0..max_transfers_per_week is available in every hypothetical GW;
    - a weak individual downgrade is allowed if it finances a stronger bundle;
    - squad, budget, FT, hits, XI, captain and vice-captain are optimized jointly;
    - current deadline prices are frozen throughout the hypothetical horizon;
    - only the first action is intended to be executed before replanning.

    Initial players retain their true FPL sale values until sold. A player bought
    during the hypothetical path is tracked as newly owned and later sells at the
    same frozen current price, which is exact under the frozen-price assumption.
    """
    if not valid_squad(meta, state.squad):
        raise ValueError("joint planner requires a valid 15-player starting squad")

    available = set(int(gw) for gw in origin.gw.unique())
    gws = [
        gw for gw in range(int(current_gw), int(current_gw) + len(config.weights))
        if gw in available
    ]
    if not gws:
        return PlannerResult(int(current_gw), (), (), 0.0, [])

    weights = list(config.weights[: len(gws)])
    meta_u = meta.drop_duplicates("id").copy()
    required = {"id", "web_name", "team", "position", "price_tenths"}
    missing_cols = required - set(meta_u.columns)
    if missing_cols:
        raise ValueError(f"joint planner metadata missing columns: {sorted(missing_cols)}")

    meta_u = meta_u[meta_u.position.isin(POSITION_COUNTS)].copy()
    meta_u["id"] = meta_u.id.astype(int)
    meta_u["price_tenths"] = meta_u.price_tenths.astype(int)
    player_ids = meta_u.id.astype(int).tolist()
    id_to_i = {pid: i for i, pid in enumerate(player_ids)}
    owned0 = set(map(int, state.squad))
    if not owned0.issubset(id_to_i):
        raise RuntimeError(f"joint planner missing owned players: {sorted(owned0 - set(id_to_i))}")

    n = len(player_ids)
    h = len(gws)
    xp, pplay = _forecast_arrays(origin, meta_u, player_ids, gws)
    prices = meta_u.price_tenths.to_numpy(int)
    positions = meta_u.position.astype(str).to_numpy()
    teams = meta_u.team.to_numpy()

    legacy0 = np.array([1 if pid in owned0 else 0 for pid in player_ids], dtype=float)
    new0 = np.zeros(n, dtype=float)
    legacy_sale = np.zeros(n, dtype=float)
    for i, pid in enumerate(player_ids):
        if pid in owned0:
            legacy_sale[i] = selling_price(
                int(state.squad[pid].purchase_price), int(prices[i])
            )

    # Variable blocks, each H*N unless noted:
    # legacy ownership, new ownership, buy, sell legacy, sell new,
    # XI, captain, vice, captain*vice_score auxiliary;
    # then vice score [H], bank [H], FT/transfer transition q [H*36].
    block = h * n
    off_legacy = 0
    off_new = off_legacy + block
    off_buy = off_new + block
    off_sell_legacy = off_buy + block
    off_sell_new = off_sell_legacy + block
    off_xi = off_sell_new + block
    off_cap = off_xi + block
    off_vice = off_cap + block
    off_cap_vscore = off_vice + block
    off_vscore = off_cap_vscore + block
    off_bank = off_vscore + h
    off_q = off_bank + h
    q_states = [(ft, tr) for ft in range(6) for tr in range(config.max_transfers_per_week + 1)]
    q_count = len(q_states)
    total_vars = off_q + h * q_count

    def idx(base: int, g: int, i: int) -> int:
        return base + g * n + i

    def qidx(g: int, qi: int) -> int:
        return off_q + g * q_count + qi

    c = np.zeros(total_vars, dtype=float)
    integrality = np.ones(total_vars, dtype=int)
    lb = np.zeros(total_vars, dtype=float)
    ub = np.ones(total_vars, dtype=float)

    # Continuous variables.
    integrality[off_cap_vscore:off_vscore] = 0
    integrality[off_vscore:off_bank] = 0
    integrality[off_bank:off_q] = 0

    max_bank = float(state.bank + np.sum(prices) + np.sum(legacy_sale) + 1000)
    lb[off_bank:off_q] = 0.0
    ub[off_bank:off_q] = max_bank

    # q variables binary; disable transfer counts above configured max implicitly
    # by constructing only those states.
    # Forecast objective: weighted XI + exact captain/vice fallback.
    for g, weight in enumerate(weights):
        c[off_xi + g * n : off_xi + (g + 1) * n] = -float(weight) * xp[g]
        c[off_cap + g * n : off_cap + (g + 1) * n] = -float(weight) * xp[g]

        v_lo = float(np.min(xp[g])) if n else 0.0
        v_hi = float(np.max(xp[g])) if n else 0.0
        lo_t, hi_t = min(0.0, v_lo), max(0.0, v_hi)
        lb[off_vscore + g] = v_lo
        ub[off_vscore + g] = v_hi
        lb[off_cap_vscore + g * n : off_cap_vscore + (g + 1) * n] = lo_t
        ub[off_cap_vscore + g * n : off_cap_vscore + (g + 1) * n] = hi_t
        c[off_cap_vscore + g * n : off_cap_vscore + (g + 1) * n] = (
            -float(weight) * (1.0 - pplay[g])
        )

        # Deterministic hit + uncertainty cost is deliberately NOT multiplied
        # by the horizon weight.
        for qi, (ft, tr) in enumerate(q_states):
            paid = max(0, int(tr) - int(ft))
            c[qidx(g, qi)] = (4.0 + float(config.hit_uncertainty_buffer)) * paid

    rows: list[dict[int, float]] = []
    lower: list[float] = []
    upper: list[float] = []

    def add(coeffs: dict[int, float], lo: float, hi: float) -> None:
        rows.append(coeffs)
        lower.append(float(lo))
        upper.append(float(hi))

    # Ownership transitions and no simultaneous buy/sell.
    for g in range(h):
        for i in range(n):
            # legacy_after + sell_legacy = legacy_before
            coeff = {idx(off_legacy, g, i): 1.0, idx(off_sell_legacy, g, i): 1.0}
            if g == 0:
                rhs = legacy0[i]
            else:
                coeff[idx(off_legacy, g - 1, i)] = -1.0
                rhs = 0.0
            add(coeff, rhs, rhs)

            # new_after - buy + sell_new = new_before
            coeff = {
                idx(off_new, g, i): 1.0,
                idx(off_buy, g, i): -1.0,
                idx(off_sell_new, g, i): 1.0,
            }
            if g == 0:
                rhs = new0[i]
            else:
                coeff[idx(off_new, g - 1, i)] = -1.0
                rhs = 0.0
            add(coeff, rhs, rhs)

            # At most one ownership type and no pointless same-GW round trip.
            add(
                {idx(off_legacy, g, i): 1.0, idx(off_new, g, i): 1.0},
                -np.inf, 1.0,
            )
            add(
                {
                    idx(off_buy, g, i): 1.0,
                    idx(off_sell_legacy, g, i): 1.0,
                    idx(off_sell_new, g, i): 1.0,
                },
                -np.inf, 1.0,
            )

    # Squad composition and club limit in every hypothetical GW.
    for g in range(h):
        for position, count in POSITION_COUNTS.items():
            coeff = {}
            for i in np.flatnonzero(positions == position):
                coeff[idx(off_legacy, g, int(i))] = 1.0
                coeff[idx(off_new, g, int(i))] = 1.0
            add(coeff, float(count), float(count))

        for team in pd.unique(teams):
            coeff = {}
            for i in np.flatnonzero(teams == team):
                coeff[idx(off_legacy, g, int(i))] = 1.0
                coeff[idx(off_new, g, int(i))] = 1.0
            add(coeff, -np.inf, 3.0)

        # Buys and sells balance, and transfer count is selected through q.
        coeff = {}
        for i in range(n):
            coeff[idx(off_buy, g, i)] = 1.0
            coeff[idx(off_sell_legacy, g, i)] = -1.0
            coeff[idx(off_sell_new, g, i)] = -1.0
        add(coeff, 0.0, 0.0)

        coeff = {idx(off_buy, g, i): 1.0 for i in range(n)}
        for qi, (_ft, tr) in enumerate(q_states):
            coeff[qidx(g, qi)] = -float(tr)
        add(coeff, 0.0, 0.0)

        # Exactly one FT/transfer-count transition state.
        add({qidx(g, qi): 1.0 for qi in range(q_count)}, 1.0, 1.0)
        if g == 0 and config.first_gw_max_transfers is not None:
            disallowed = {
                qidx(g, qi): 1.0
                for qi, (_ft, tr) in enumerate(q_states)
                if tr > int(config.first_gw_max_transfers)
            }
            if disallowed:
                add(disallowed, 0.0, 0.0)

        # Exact FT state transition.
        if g == 0:
            add(
                {qidx(g, qi): float(ft) for qi, (ft, _tr) in enumerate(q_states)},
                float(state.free_transfers), float(state.free_transfers),
            )
        else:
            coeff = {
                qidx(g, qi): float(ft)
                for qi, (ft, _tr) in enumerate(q_states)
            }
            for qi, (ft, tr) in enumerate(q_states):
                nxt = next_free_transfers(ft, tr)
                coeff[qidx(g - 1, qi)] = coeff.get(qidx(g - 1, qi), 0.0) - float(nxt)
            add(coeff, 0.0, 0.0)

        # Frozen-deadline budget accounting.
        coeff = {off_bank + g: 1.0}
        if g > 0:
            coeff[off_bank + g - 1] = -1.0
            rhs = 0.0
        else:
            rhs = float(state.bank)
        for i in range(n):
            if legacy_sale[i] != 0.0:
                coeff[idx(off_sell_legacy, g, i)] = -float(legacy_sale[i])
            coeff[idx(off_sell_new, g, i)] = -float(prices[i])
            coeff[idx(off_buy, g, i)] = float(prices[i])
        add(coeff, rhs, rhs)

        # XI and exact captain/vice structure.
        add({idx(off_xi, g, i): 1.0 for i in range(n)}, 11.0, 11.0)
        add({idx(off_cap, g, i): 1.0 for i in range(n)}, 1.0, 1.0)
        add({idx(off_vice, g, i): 1.0 for i in range(n)}, 1.0, 1.0)

        for position in START_MIN:
            coeff = {
                idx(off_xi, g, int(i)): 1.0
                for i in np.flatnonzero(positions == position)
            }
            add(coeff, float(START_MIN[position]), float(START_MAX[position]))

        for i in range(n):
            # starter <= owned
            add(
                {
                    idx(off_xi, g, i): 1.0,
                    idx(off_legacy, g, i): -1.0,
                    idx(off_new, g, i): -1.0,
                },
                -np.inf, 0.0,
            )
            add(
                {idx(off_cap, g, i): 1.0, idx(off_xi, g, i): -1.0},
                -np.inf, 0.0,
            )
            add(
                {idx(off_vice, g, i): 1.0, idx(off_xi, g, i): -1.0},
                -np.inf, 0.0,
            )
            add(
                {idx(off_cap, g, i): 1.0, idx(off_vice, g, i): 1.0},
                -np.inf, 1.0,
            )

        # vice_score = sum_j xP_j * vice_j
        coeff = {off_vscore + g: 1.0}
        for i in range(n):
            coeff[idx(off_vice, g, i)] = -float(xp[g, i])
        add(coeff, 0.0, 0.0)

        # t_i = captain_i * vice_score, exact McCormick envelope because
        # captain_i is binary and vice_score has known [L,U] bounds.
        L = float(np.min(xp[g])) if n else 0.0
        U = float(np.max(xp[g])) if n else 0.0
        V = off_vscore + g
        for i in range(n):
            C = idx(off_cap, g, i)
            T = idx(off_cap_vscore, g, i)
            add({T: 1.0, C: -U}, -np.inf, 0.0)          # T <= U*C
            add({T: 1.0, C: -L}, 0.0, np.inf)           # T >= L*C
            add({T: 1.0, V: -1.0, C: -L}, -np.inf, -L) # T <= V-L(1-C)
            add({T: 1.0, V: -1.0, C: -U}, -U, np.inf)  # T >= V-U(1-C)

    A = lil_matrix((len(rows), total_vars), dtype=float)
    for r, coeff in enumerate(rows):
        if coeff:
            js = np.fromiter(coeff.keys(), dtype=int)
            vs = np.fromiter(coeff.values(), dtype=float)
            A[r, js] = vs

    result = milp(
        c=c,
        integrality=integrality,
        bounds=Bounds(lb, ub),
        constraints=LinearConstraint(A.tocsr(), np.asarray(lower), np.asarray(upper)),
        options={
            "time_limit": float(config.time_limit),
            "mip_rel_gap": float(config.mip_rel_gap),
        },
    )
    if result.x is None:
        raise RuntimeError(f"joint planner found no feasible incumbent: {result.message}")

    x = result.x
    path: list[TransferAction] = []
    for g, gw in enumerate(gws):
        incoming = tuple(sorted(
            player_ids[i] for i in range(n) if x[idx(off_buy, g, i)] > 0.5
        ))
        outgoing = tuple(sorted(
            player_ids[i] for i in range(n)
            if x[idx(off_sell_legacy, g, i)] > 0.5 or x[idx(off_sell_new, g, i)] > 0.5
        ))
        squad = [
            player_ids[i] for i in range(n)
            if x[idx(off_legacy, g, i)] + x[idx(off_new, g, i)] > 0.5
        ]
        selected_q = int(np.argmax([
            x[qidx(g, qi)] for qi in range(q_count)
        ]))
        ft_before, transfers = q_states[selected_q]
        paid = max(0, int(transfers) - int(ft_before))
        official_hit = 4 * paid
        uncertainty = float(config.hit_uncertainty_buffer) * paid
        manager_score = projected_manager_score(origin, meta_u, squad, int(gw))
        bank_before = int(state.bank if g == 0 else round(x[off_bank + g - 1]))
        bank_after = int(round(x[off_bank + g]))
        ft_after = next_free_transfers(ft_before, transfers)
        path.append(TransferAction(
            gw=int(gw),
            outgoing=outgoing,
            incoming=incoming,
            transfers=int(transfers),
            official_hit_points=int(official_hit),
            uncertainty_penalty=float(uncertainty),
            projected_manager_score=float(manager_score),
            utility_this_gw=float(manager_score - official_hit - uncertainty),
            free_transfers_before=int(ft_before),
            free_transfers_after=int(ft_after),
            bank_before=int(bank_before),
            bank_after=int(bank_after),
        ))

    # Report the maximized utility in the same sign convention as PlannerResult.
    objective = float(-result.fun)
    return PlannerResult(
        current_gw=int(current_gw),
        horizon_gws=tuple(gws),
        weights=tuple(weights),
        objective=objective,
        path=path,
    )
