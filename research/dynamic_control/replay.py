"""Historical diagnostic using an external, unchanged research replay checkout."""
import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parents[1] / "integration/research-data/frozen-ts-config.json"


def extend(origin, historical, gw, horizon, learn):
    """Extend the last visible player-GW forecast, using only older vintages."""
    import pandas as pd

    last = int(origin.gw.max())
    targets = range(last + 1, min(38, gw + horizon - 1) + 1)
    if not targets:
        return origin, 0, 1.0
    factor = 1.0
    n = 0
    if learn:
        # Compare the same targets at two adjacent historical issue vintages.
        # Restrict to established rows in the calibration pairs.
        old = historical[(historical.gw - historical.origin_gw == 6) &
                         (historical.origin_gw < gw - 2)]
        new = historical[(historical.gw - historical.origin_gw == 5) &
                         (historical.origin_gw < gw - 1)]
        pairs = old.merge(new, on=["id", "gw"], suffixes=("_old", "_new"))
        pairs = pairs[pairs.xpts_mean_old > 0]
        n = len(pairs)
        if n:
            factor = float((pairs.xpts_mean_old @ pairs.xpts_mean_new) /
                           (pairs.xpts_mean_old @ pairs.xpts_mean_old))
    tail = origin[origin.gw.eq(last)]
    return pd.concat([origin, *(tail.assign(gw=t, xpts_mean=tail.xpts_mean * factor)
                                for t in targets)], ignore_index=True), n, factor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("arm", choices=["tsv3", "equal6", "mpc10", "terminal8"])
    args = parser.parse_args()
    source = args.source.resolve()
    sys.path[:0] = [str(source / "scripts"), str(source / "src")]
    import pandas as pd
    import run_transfer_strategy_v3_replay as legacy
    import run_horizon_policy_comparison as hp
    from fpl_xpts.optimize import plan_squad
    from fpl_xpts.season_replay import actual_team_points, initial_squad, legalize_team_limit, valid_squad
    from fpl_xpts.transfer_planner import PlannerConfig, execute_first_action, plan_transfer_path

    metadata = hp.unpack_runtime("merged_gw.csv")[["GW", "element", "team", "position", "value"]]
    names = hp.unpack_runtime("players_raw.csv").set_index("id").web_name.astype(str).to_dict()
    forecasts = hp.rolling_forecast()[["id", "web_name", "position", "gw", "origin_gw",
                                       "xpts_mean", "p_play", "fixtures"]].copy()
    forecasts.id = forecasts.id.astype(int)
    if forecasts.duplicated(["origin_gw", "gw", "id"]).any():
        raise ValueError("Expected one forecast per player, target and vintage")
    # Ground-truth columns are never passed to planning. First-week roster is
    # a fixed seed shared by all arms. Later prices/clubs come from past GWs.
    manifest = json.loads(CONFIG.read_text())
    manifest["weights"] = tuple(manifest["weights"])
    frozen = PlannerConfig(**manifest)
    variant = args.arm
    horizon = {"tsv3": 6, "equal6": 6, "mpc10": 10, "terminal8": 8}[variant]
    # terminal8 treats the two appended weeks as a short continuation rollout
    # with an empirically calibrated tail. It keeps two full transfer stages.
    config = frozen if variant == "tsv3" else replace(frozen, weights=(1.0,) * horizon)
    known = hp.gw_meta(metadata, names, 1)
    first = hp.complete_current_projection(forecasts[forecasts.origin_gw.eq(0)], known, 1)
    state = initial_squad(first, known, [1])
    initial = {pid: item.purchase_price for pid, item in state.squad.items()}
    starting_bank, starting_ft = state.bank, state.free_transfers
    logs = []
    nominations = []
    for gw in range(1, 39):
        start = perf_counter()
        if gw > 2:
            observed = hp.gw_meta(metadata, names, gw - 1)
            known = pd.concat([known[~known.id.isin(observed.id)], observed], ignore_index=True)
        origin = legacy.origin_with_meta(forecasts, known, gw)
        origin = origin[origin.id.isin(known.id)].copy()
        current = hp.complete_current_projection(forecasts[forecasts.origin_gw.eq(gw - 1)], known, gw)
        # Complete the lineup view against exactly the same eligible metadata.
        current = current[current.id.isin(known.id)]
        origin, samples, factor = extend(origin, forecasts, gw, horizon, variant == "terminal8")
        before = state.free_transfers
        forced = legalize_team_limit(state, known, origin, gw)
        state.free_transfers = max(0, before - len(forced))
        week_config = config if not forced else replace(config, max_transfers_per_week=5 - len(forced))
        result = plan_transfer_path(state, known, origin, gw, week_config)
        moves = execute_first_action(state, result, known)
        hits = sum(int(move["hit"]) for move in forced + moves)
        if not valid_squad(known, state.squad) or state.bank < 0 or hits != 4 * max(0, len(forced + moves) - before):
            raise RuntimeError(f"Invalid transfer accounting in GW{gw}")
        plan = plan_squad(current, list(state.squad), gw)
        captain = int(plan.rows.loc[plan.rows.role.eq("C"), "id"].iloc[0])
        nominations.append((gw, plan.rows, hits))
        logs.append(dict(arm=args.arm, gw=gw, transfers=len(forced + moves), hits=hits,
                         forced=len(forced), bank=state.bank, ft_before=before,
                         ft_after=state.free_transfers, incoming=";".join(str(m["in_id"]) for m in forced + moves),
                         outgoing=";".join(str(m["out_id"]) for m in forced + moves),
                         captain=captain, projection=plan.expected_score,
                         tail_samples=samples, tail_factor=factor, seconds=perf_counter() - start))
        print(args.arm, gw, flush=True)
    # Scoring accesses the actual-result columns only after decisions are locked.
    outcomes = hp.unpack_runtime("merged_gw.csv")
    for log, (gw, plan, hits) in zip(logs, nominations, strict=True):
        log["points"], _ = actual_team_points(plan, hp.actual_gw(outcomes, gw), None, hits)
    args.output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(logs).to_csv(args.output / f"{args.arm}.csv", index=False)
    sources = [
        "src/fpl_xpts/transfer_planner.py", "src/fpl_xpts/season_replay.py",
        "src/fpl_xpts/optimize.py", "scripts/run_transfer_strategy_v3_replay.py",
        "scripts/run_horizon_policy_comparison.py",
        "analysis/results/legacy-rolling-recovery-v1/manifest.json",
        "analysis/results/legacy-season-technical-replay-v1/runtime_input_manifest.json",
    ]
    receipt = dict(initial=initial, bank=starting_bank, free_transfers=starting_ft, config=vars(config),
                   sha256={p: sha256((source / p).read_bytes()).hexdigest() for p in sources})
    (args.output / f"{args.arm}.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
