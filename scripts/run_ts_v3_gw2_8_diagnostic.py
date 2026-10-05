#!/usr/bin/env python3
"""Targeted TS v3 diagnostic: candidate coverage vs transfer-cost discounting.

Point model is untouched. This script replays the baseline TS v3 state and,
for GW2-GW8, asks two separate questions from the SAME pre-deadline state:

1) Candidate coverage:
   - what immediate squad would the TS v2 static lineup-aware optimizer choose?
   - is that exact squad proposed by TS v3's fast-local candidate generator?
   - if forcibly injected as TS v3's first action, what 6GW path objective results?

2) Objective accounting:
   - does TS v3 change its first action when forecast points are horizon-weighted
     but deterministic hit/buffer costs are NOT horizon-discounted?

This is a diagnostic only; baseline defaults remain unchanged.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_horizon_policy_comparison as hp
import run_transfer_strategy_v2_grid as tsv2
import run_transfer_strategy_v3_replay as tsv3

from fpl_xpts.optimize import plan_squad
from fpl_xpts.season_replay import actual_team_points, initial_squad, legalize_team_limit
from fpl_xpts.transfer_planner import (
    PlannerConfig,
    _apply_selected_squad,
    _fast_local_candidate_squads,
    _prepare_local_candidates,
    clone_state,
    execute_first_action,
    next_free_transfers,
    plan_transfer_path,
    projected_manager_score,
    transfer_penalties,
)
from run_v4rc_experiment import write_json

OUT = ROOT / "analysis/results/ts-v3-gw2-8-diagnostic-20261005-v1"
WEIGHTS = (1.00, .85, .70, .55, .40, .25)
BUFFER = 1.5
TARGET_GWS = set(range(2, 9))


def cfg(discount_transfer_costs: bool = True, weights=WEIGHTS) -> PlannerConfig:
    return PlannerConfig(
        weights=tuple(weights),
        hit_uncertainty_buffer=BUFFER,
        beam_width=20,
        candidates_per_transfer_count=1,
        candidate_limit_per_position=18,
        top_targets_per_position=18,
        local_bundle_beam=60,
        candidate_return_per_depth=12,
        max_transfers_per_week=5,
        candidate_backend="fast_local",
        discount_transfer_costs=bool(discount_transfer_costs),
        milp_time_limit=2.0,
    )


def action_dict(action):
    if action is None:
        return dict(transfers=0, outgoing=[], incoming=[], hit=0, buffer=0.0)
    return dict(
        transfers=int(action.transfers),
        outgoing=list(map(int, action.outgoing)),
        incoming=list(map(int, action.incoming)),
        hit=int(action.official_hit_points),
        buffer=float(action.uncertainty_penalty),
        projected_manager_score=float(action.projected_manager_score),
        ft_before=int(action.free_transfers_before),
        ft_after=int(action.free_transfers_after),
        bank_before=int(action.bank_before),
        bank_after=int(action.bank_after),
    )


def names_for(meta, ids):
    by = meta.drop_duplicates("id").set_index("id").web_name.astype(str).to_dict()
    return [by.get(int(pid), str(pid)) for pid in ids]


def immediate_actual(state_before, selected, meta, current, actual, hit_points):
    test = clone_state(state_before)
    after, _, _ = _apply_selected_squad(test, set(map(int, selected)), meta)
    plan = plan_squad(current, list(after.squad), int(current.gw.iloc[0]))
    score, _ = actual_team_points(plan.rows, actual, None, int(hit_points))
    return int(score)


def injected_objective(state, meta, origin, gw, selected, config):
    """Force one immediate squad, then optimize the remaining original horizon."""
    after, outgoing, incoming = _apply_selected_squad(
        clone_state(state), set(map(int, selected)), meta
    )
    transfers = len(incoming)
    hit, uncertainty = transfer_penalties(
        state.free_transfers, transfers, config.hit_uncertainty_buffer
    )
    score = projected_manager_score(origin, meta, after.squad, gw)
    if config.discount_transfer_costs:
        first = float(config.weights[0]) * float(score - hit - uncertainty)
    else:
        first = float(config.weights[0]) * float(score) - hit - uncertainty
    after.free_transfers = next_free_transfers(state.free_transfers, transfers)

    tail = tuple(config.weights[1:])
    if not tail:
        return first
    continuation = plan_transfer_path(
        after, meta, origin, gw + 1, replace(config, weights=tail)
    )
    return float(first + continuation.objective)


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    OUT.mkdir(parents=True)

    gws, names, forecast = tsv3.prepare()
    meta1 = hp.gw_meta(gws, names, 1)
    origin1 = hp.complete_current_projection(forecast[forecast.origin_gw == 0], meta1, 1)
    state = initial_squad(origin1, meta1, [1])
    known = meta1.copy()
    rows = []
    detail = []

    baseline_cfg = cfg(True)
    no_discount_cfg = cfg(False)

    for gw in range(1, 9):
        obs = hp.gw_meta(gws, names, gw)
        known = pd.concat(
            [known[~known.id.isin(obs.id)], obs], ignore_index=True
        ).drop_duplicates("id", keep="last")
        meta = known.copy()
        origin_raw = forecast[forecast.origin_gw == gw - 1].copy()
        current = hp.complete_current_projection(origin_raw, meta, gw)
        origin = tsv3.origin_with_meta(forecast, meta, gw)
        actual = hp.actual_gw(gws, gw)

        forced = []
        if gw > 1:
            forced = legalize_team_limit(state, meta, origin, gw)

        pre = clone_state(state)
        baseline = plan_transfer_path(pre, meta, origin, gw, baseline_cfg)

        if gw in TARGET_GWS:
            alt = plan_transfer_path(pre, meta, origin, gw, no_discount_cfg)

            # Apply the TS v2 static optimizer to the SAME TS v3 pre-state.
            static_state = clone_state(pre)
            static_rows = tsv2.best_manager_bundle(
                static_state, meta, origin, gw, WEIGHTS, BUFFER, max_total=5, already=0
            )
            static_selected = set(static_state.squad)
            static_out = sorted(set(pre.squad) - static_selected)
            static_in = sorted(static_selected - set(pre.squad))
            static_hit = sum(int(x.get("hit", 0)) for x in static_rows)

            available = set(int(x) for x in origin.gw.unique())
            horizon = [x for x in range(gw, gw + len(WEIGHTS)) if x in available]
            ww = list(WEIGHTS[:len(horizon)])
            prepared = _prepare_local_candidates(
                meta, origin, horizon, ww, baseline_cfg.top_targets_per_position
            )
            candidates = _fast_local_candidate_squads(
                pre, meta, origin, horizon, ww,
                baseline_cfg.max_transfers_per_week,
                baseline_cfg.top_targets_per_position,
                baseline_cfg.local_bundle_beam,
                baseline_cfg.candidate_return_per_depth,
                prepared,
            )
            candidate_keys = {tuple(sorted(x)) for x in candidates}
            static_in_candidates = tuple(sorted(static_selected)) in candidate_keys

            base_selected = (
                (set(pre.squad) - set(baseline.first_action.outgoing))
                | set(baseline.first_action.incoming)
                if baseline.first_action else set(pre.squad)
            )
            alt_selected = (
                (set(pre.squad) - set(alt.first_action.outgoing))
                | set(alt.first_action.incoming)
                if alt.first_action else set(pre.squad)
            )

            static_obj_discount = injected_objective(
                pre, meta, origin, gw, static_selected, baseline_cfg
            )
            static_obj_nodiscount = injected_objective(
                pre, meta, origin, gw, static_selected, no_discount_cfg
            )

            base_actual = immediate_actual(
                pre, base_selected, meta, current, actual,
                baseline.first_action.official_hit_points if baseline.first_action else 0,
            )
            alt_actual = immediate_actual(
                pre, alt_selected, meta, current, actual,
                alt.first_action.official_hit_points if alt.first_action else 0,
            )
            static_actual = immediate_actual(
                pre, static_selected, meta, current, actual, static_hit
            )

            row = dict(
                gw=gw,
                ft_before=int(pre.free_transfers),
                bank_before=float(pre.bank) / 10.0,
                candidate_count=len(candidates),
                static_candidate_present=bool(static_in_candidates),
                baseline_transfers=baseline.first_action.transfers if baseline.first_action else 0,
                nodiscount_transfers=alt.first_action.transfers if alt.first_action else 0,
                static_transfers=len(static_in),
                baseline_hit=baseline.first_action.official_hit_points if baseline.first_action else 0,
                nodiscount_hit=alt.first_action.official_hit_points if alt.first_action else 0,
                static_hit=static_hit,
                baseline_objective=float(baseline.objective),
                nodiscount_objective=float(alt.objective),
                injected_static_objective_discounted=float(static_obj_discount),
                injected_static_objective_nodiscount=float(static_obj_nodiscount),
                baseline_actual_current_gw=base_actual,
                nodiscount_actual_current_gw=alt_actual,
                static_actual_current_gw=static_actual,
                baseline_vs_static_injected_objective=float(baseline.objective - static_obj_discount),
                nodiscount_vs_static_injected_objective=float(alt.objective - static_obj_nodiscount),
            )
            rows.append(row)
            detail.append(dict(
                **row,
                baseline=action_dict(baseline.first_action),
                baseline_out_names=names_for(meta, baseline.first_action.outgoing if baseline.first_action else []),
                baseline_in_names=names_for(meta, baseline.first_action.incoming if baseline.first_action else []),
                nodiscount=action_dict(alt.first_action),
                nodiscount_out_names=names_for(meta, alt.first_action.outgoing if alt.first_action else []),
                nodiscount_in_names=names_for(meta, alt.first_action.incoming if alt.first_action else []),
                static_out=static_out,
                static_in=static_in,
                static_out_names=names_for(meta, static_out),
                static_in_names=names_for(meta, static_in),
                baseline_path=[action_dict(x) for x in baseline.path],
                nodiscount_path=[action_dict(x) for x in alt.path],
            ))

        # Evolve the true baseline TS v3 state only.
        execute_first_action(state, baseline, meta)

    table = pd.DataFrame(rows)
    table.to_csv(OUT / "summary.csv", index=False)
    write_json(OUT / "detail.json", detail)

    summary = {
        "classification": "targeted TS v3 diagnostic; point model unchanged",
        "gws": sorted(TARGET_GWS),
        "questions": {
            "candidate_coverage": "Does the TS v2-style static optimum from the same TS v3 pre-state appear in the fast-local candidate set?",
            "cost_discount": "Does removing horizon discount from deterministic hit/buffer costs materially change the TS v3 first action/path?",
        },
        "rows": rows,
        "counts": {
            "static_candidate_present": int(table.static_candidate_present.sum()),
            "static_candidate_missing": int((~table.static_candidate_present).sum()),
            "nodiscount_changes_first_transfer_count": int((table.baseline_transfers != table.nodiscount_transfers).sum()),
        },
        "note": "Actual-current-GW columns are retrospective diagnostics only, not optimization targets.",
    }
    write_json(OUT / "summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
