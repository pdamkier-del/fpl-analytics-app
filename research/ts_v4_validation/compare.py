"""Run PR64's historical replay with one controlled change at a time."""
import argparse
from contextlib import contextmanager
import csv
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

PR64 = "01bcaba225c111b222f3b329a3e18245a4f14835"
LEGACY = "6d875a65251fb62f691dc0386ea81aeb29d27c0f"
ARMS = {"tsv3": .60, "rho70": .70, "rho80": .80, "rho90": .90, "rho100": 1.,
        "discount_costs": .60, "zero_buffer": .60}


def check_pin(path, revision):
    actual = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    if actual != revision or subprocess.check_output(["git", "-C", str(path), "diff", "HEAD", "--"]):
        raise ValueError(f"Expected clean source checkout at {revision}: {path}")


def weights(rho):
    return tuple(round(rho ** step, 12) for step in range(6))


def variant(config, arm):
    if arm == "discount_costs":
        return replace(config, discount_transfer_costs=True)
    if arm == "zero_buffer":
        return replace(config, hit_uncertainty_buffer=0.)
    return replace(config, weights=weights(ARMS[arm]))


@contextmanager
def fixed_proposer(planner, origin_gw, fixed_weights):
    """Hold fast-local's shortlist weights fixed while varying the outer objective."""
    prepare = planner._prepare_local_candidates
    generate = planner._fast_local_candidate_squads

    def suffix(gws):
        offset = gws[0] - origin_gw
        if offset < 0 or list(gws) != list(range(gws[0], gws[0] + len(gws))):
            raise ValueError("Expected contiguous forecast GWs")
        result = fixed_weights[offset:offset + len(gws)]
        if len(result) != len(gws):
            raise ValueError("Unexpected shortlist horizon")
        return result

    def prepare_fixed(meta, origin, gws, _weights, top):
        return prepare(meta, origin, gws, suffix(gws), top)

    def generate_fixed(state, meta, origin, gws, _weights, *settings):
        return generate(state, meta, origin, gws, suffix(gws), *settings)

    with patch.object(planner, "_prepare_local_candidates", prepare_fixed), patch.object(
            planner, "_fast_local_candidate_squads", generate_fixed):
        yield


def run_arm(pr64, source, output, arm):
    sys.path[:0] = [str(pr64 / "research/dynamic_control"), str(source / "src")]
    import replay
    from fpl_xpts import transfer_planner as planner

    if arm == "tsv3":
        for suffix in (".csv", ".json"):
            shutil.copyfile(pr64 / f"research/dynamic_control/results/tsv3{suffix}", output / f"tsv3{suffix}")
        return
    original = planner.plan_transfer_path

    def plan(state, meta, projections, gw, config):
        with fixed_proposer(planner, gw, config.weights):
            return original(state, meta, projections, gw, variant(config, arm))

    scratch = output / arm
    scratch.mkdir(exist_ok=False)
    with patch.object(planner, "plan_transfer_path", plan), patch.object(
            sys, "argv", ["replay.py", str(source), str(scratch), "tsv3"]):
        replay.main()
    source_csv = scratch / "tsv3.csv"
    with source_csv.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    with (output / f"{arm}.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, list(rows[0]))
        writer.writeheader()
        writer.writerows({**row, "arm": arm} for row in rows)
    receipt = json.loads((scratch / "tsv3.json").read_text())
    frozen = dict(receipt["config"])
    frozen["weights"] = tuple(frozen["weights"])
    receipt["config"] = vars(variant(planner.PlannerConfig(**frozen), arm))
    receipt["proposal_weights"] = list(frozen["weights"])
    (output / f"{arm}.json").write_text(json.dumps(receipt, indent=2) + "\n")


def audit(pr64, source, output):
    sys.path.insert(0, str(pr64 / "research/dynamic_control"))
    import audit_replay
    import pandas as pd

    baseline = json.loads((output / "tsv3.json").read_text())
    for arm in ARMS:
        doc = json.loads((output / f"{arm}.json").read_text())
        changed = {key for key, value in doc["config"].items() if value != baseline["config"][key]}
        expected = {"tsv3": set(), "discount_costs": {"discount_transfer_costs"},
                    "zero_buffer": {"hit_uncertainty_buffer"}}.get(arm, {"weights"})
        if changed != expected or doc.get("proposal_weights", baseline["config"]["weights"]) != baseline["config"]["weights"]:
            raise ValueError(f"Incomparable arm {arm}")
    with patch.object(audit_replay, "ARMS", tuple(ARMS)):
        audit_replay.audit(source, output)
    weekly = pd.read_csv(output / "historical-weekly.csv")
    ledgers = {arm: pd.read_csv(output / f"{arm}.csv", keep_default_na=False) for arm in ARMS}
    basic = json.loads((output / "historical-summary.json").read_text())
    summary = []
    for row in basic:
        arm = row["arm"]
        path = ledgers[arm]
        same = path[["incoming", "outgoing"]].eq(ledgers["tsv3"][["incoming", "outgoing"]]).all(axis=1)
        summary.append({
            **{key: value for key, value in row.items() if key not in ("tc_gw", "tc_gain", "points_with_tc")},
            "rho": ARMS[arm],
            "gross_points": row["points"] + row["hits"],
            "weeks_with_hits": int(path.hits.gt(0).sum()),
            "first_gw_different_from_tsv3": None if same.all() else int(path.loc[~same, "gw"].min()),
            "p90_seconds": float(path.seconds.quantile(.90)),
            "config": json.loads((output / f"{arm}.json").read_text())["config"],
            "baseline_ledger_reused": arm == "tsv3",
        })
    actions = pd.concat(ledgers.values(), ignore_index=True)
    checked = actions.merge(weekly[["arm", "gw", "hold_points", "same_state_gain",
                                    "same_state_expected_gain", "short_holds"]],
                            on=["arm", "gw"], validate="one_to_one")
    checked.to_csv(output / "decisions.csv", index=False, float_format="%.9g")
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pr64", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("arm", choices=[*ARMS, "audit"])
    args = parser.parse_args()
    check_pin(args.pr64, PR64)
    check_pin(args.source, LEGACY)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.arm == "audit":
        audit(args.pr64.resolve(), args.source.resolve(), args.output)
    else:
        run_arm(args.pr64.resolve(), args.source.resolve(), args.output.resolve(), args.arm)
