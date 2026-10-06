#!/usr/bin/env python3
"""Real-data single-deadline smoke test for TS v4 joint MILP.

This intentionally runs GW1 only. It does NOT start or advance a season replay.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as v3

from fpl_xpts.season_replay import initial_squad
from fpl_xpts.transfer_planner_joint import JointPlannerConfig, plan_transfer_path_joint


def main():
    gws, names, forecast = v3.prepare()
    meta = hp.gw_meta(gws, names, 1)
    origin0 = hp.complete_current_projection(forecast[forecast.origin_gw == 0], meta, 1)
    state = initial_squad(origin0, meta, [1])
    origin = v3.origin_with_meta(forecast, meta, 1)

    cfg = JointPlannerConfig(
        weights=(1.00, .85, .70, .55, .40, .25),
        hit_uncertainty_buffer=1.5,
        max_transfers_per_week=5,
        time_limit=60.0,
        mip_rel_gap=0.002,
    )
    t0 = time.perf_counter()
    result = plan_transfer_path_joint(state, meta, origin, 1, cfg)
    runtime = time.perf_counter() - t0

    payload = {
        "classification": "TS v4 single-deadline real-data smoke; NOT a season replay",
        "gw": 1,
        "runtime_seconds": runtime,
        "objective": result.objective,
        "horizon_gws": list(result.horizon_gws),
        "first_action": None if result.first_action is None else {
            "transfers": result.first_action.transfers,
            "outgoing": list(result.first_action.outgoing),
            "incoming": list(result.first_action.incoming),
            "official_hit_points": result.first_action.official_hit_points,
            "uncertainty_penalty": result.first_action.uncertainty_penalty,
            "free_transfers_before": result.first_action.free_transfers_before,
            "free_transfers_after": result.first_action.free_transfers_after,
            "bank_before": result.first_action.bank_before,
            "bank_after": result.first_action.bank_after,
        },
        "path": [
            {
                "gw": a.gw,
                "transfers": a.transfers,
                "official_hit_points": a.official_hit_points,
                "free_transfers_before": a.free_transfers_before,
                "free_transfers_after": a.free_transfers_after,
                "bank_after": a.bank_after,
            }
            for a in result.path
        ],
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
