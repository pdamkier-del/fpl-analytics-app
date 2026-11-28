"""Offline, paired TS v3 season replay and cash-shock calibration."""
import argparse
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
import gzip
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

from frontier import sale_price

HERE = Path(__file__).resolve().parent
PIN = "161b67b6fb8786a38e78c245b92a03ad841575d8"
MEASUREMENT_WEEKS = (1, 10, 20, 30)


def read_verified(root, ref):
    raw = (root / ref["file"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError(f"Hash mismatch: {ref['file']}")
    return json.loads(gzip.decompress(raw) if ref["file"].endswith(".gz") else raw)


def time(value):
    stamp = datetime.fromisoformat(value)
    if stamp.utcoffset() is None:
        raise ValueError("Timestamp requires a timezone")
    return stamp


def load_data(path, validate):
    spec = json.loads(path.read_text())
    entries = spec["seasons"]
    names = [entry["season"] for entry in entries]
    holdout = spec["holdout"]
    if (len(names) < 3 or names != sorted(set(names)) or len(holdout) < 2 or
            holdout != names[-len(holdout):] or len(holdout) == len(names)):
        raise ValueError("Require ordered seasons, with training and at least two final hold-outs")
    data = []
    for entry in entries:
        name = entry["season"]
        if (not re.fullmatch(r"20[0-9]{2}-[0-9]{2}", name) or int(name[:4]) + 1 != 2000 + int(name[-2:])
                or name < "2024-25" or entry["ft_topup_gws"] != ([16] if name == "2025-26" else [])):
            raise ValueError("Unsupported free-transfer rules")
        if set(entry["weeks"]) != set(map(str, range(1, 39))):
            raise ValueError(f"{name}: missing deadline or outcome")
        if (len(entry["cases"]) < 2 or len({c["id"] for c in entry["cases"]}) != len(entry["cases"]) or
                len({c["budget"] for c in entry["cases"]}) < 2 or
                len({tuple(sorted(c["purchases"])) for c in entry["cases"]}) < 2):
            raise ValueError(f"{name}: require distinct teams, IDs and budgets")
        weeks = {}
        for gw in range(1, 39):
            row = entry["weeks"][str(gw)]
            forecast = read_verified(path.parent, row["forecast"])
            validate(forecast)
            if (forecast["season"] != name or forecast["gws"] != list(range(gw, min(gw + 6, 39))) or
                    not time(forecast["data_asof"]) <= time(row["published_at"]) <=
                    time(row["decision_at"]) <= time(forecast["origin_deadline"]) < time(row["finalized_at"]) or
                    not row["original_receipt"] or not row["outcome_source"]):
                raise ValueError(f"{name} GW{gw}: incompatible vintage or missing provenance")
            actual = pd.DataFrame(read_verified(path.parent, row["actual"]))
            ids = [p["id"] for p in forecast["players"]]
            if (sorted(actual.id.tolist()) != sorted(set(ids)) or len(set(ids)) != len(ids) or
                    any(actual[c].isna().any() or not all(type(v) is int for v in actual[c].tolist())
                        for c in ("points", "minutes")) or (actual.minutes < 0).any()):
                raise ValueError(f"{name} GW{gw}: incomplete or invalid scoring ledger")
            weeks[gw] = forecast, actual
        if data and time(data[-1]["weeks"]["38"]["finalized_at"]) >= time(entry["weeks"]["1"]["decision_at"]):
            raise ValueError("Earlier season outcomes must be final before the next evaluation")
        data.append(dict(entry, rows=weeks))
    return data, holdout


def price_maps(entry):
    return {gw: {p["id"]: p["price_tenths"] for p in fc["players"]}
            for gw, (fc, _) in entry["rows"].items()}


def price_samples(training):
    """Prior-season empirical future movements, by horizon, position and last trend."""
    samples = defaultdict(list)
    for entry in training:
        prices = price_maps(entry)
        for gw, (forecast, _) in entry["rows"].items():
            for lag in range(1, min(6, 38 - gw) + 1):
                for p in forecast["players"]:
                    pid, pos, now = p["id"], p["position"], p["price_tenths"]
                    if pid in prices[gw + lag]:
                        delta = prices[gw + lag][pid] - now
                        trend = int(np.sign(now - prices.get(gw - 1, {}).get(pid, now)))
                        samples[lag, pos, trend].append(delta)
                        samples[lag, pos, None].append(delta)
    return samples


def terminal_bonus(samples, coefficient, prices, prior, positions, lag):
    # Compress the empirical distribution once per player. Sales are nonlinear.
    distributions = {}
    for pid, now in prices.items():
        trend = int(np.sign(now - prior.get(pid, now)))
        deltas = samples.get((lag, positions[pid], trend)) or samples[lag, positions[pid], None]
        values, counts = np.unique(np.maximum(1, now + np.asarray(deltas)), return_counts=True)
        distributions[pid] = values.tolist(), (counts / counts.sum()).tolist()
    cache = {}

    def change(pid, purchase):
        key = pid, purchase
        if key not in cache:
            values, weights = distributions[pid]
            cache[key] = sum(w * sale_price(purchase, p) for p, w in zip(values, weights)) - sale_price(purchase, prices[pid])
        return cache[key]

    return lambda squad: coefficient * sum(change(pid, player.purchase_price) for pid, player in squad.items()) / 10


@contextmanager
def add_terminal_value(planner, depth, bonus):
    """Research process only. Apply once, after all explicit forecast GW scores."""
    original = planner.PlannerNode

    def node(*args, **kwargs):
        state = original(*args, **kwargs)
        if len(state.path) == depth:
            value = bonus(state.state.squad)
            state.objective += value
            state.rank_score += value
        return state

    if bonus is not None:
        planner.PlannerNode = node
    try:
        yield
    finally:
        planner.PlannerNode = original


def capital(state, prices):
    return state.bank + sum(sale_price(p.purchase_price, prices[pid]) for pid, p in state.squad.items())


class Replay:
    def __init__(self, frozen):
        actual = subprocess.check_output(["git", "-C", frozen, "rev-parse", "HEAD"], text=True).strip()
        if actual != PIN or subprocess.check_output(
                ["git", "-C", frozen, "status", "--porcelain", "--untracked-files=no"], text=True).strip():
            raise ValueError("Require clean frozen TS checkout")
        sys.path[:0] = [str(frozen / sub) for sub in ("scripts", "src", ".")]
        from fpl_xpts import transfer_planner, season_replay, wildcard_ts_action
        from b_preview_ts import ScenarioScorer, preview_scoring, validate_forecast
        from run_live_locked_ts import cfg, project

        self.planner, self.season, self.wildcard = transfer_planner, season_replay, wildcard_ts_action
        self.scorer, self.scoring, self.validate = ScenarioScorer, preview_scoring, validate_forecast
        self.config, self.project = cfg(), project
        repo_config = HERE.parents[1] / "integration/research-data/frozen-ts-config.json"
        if json.loads(json.dumps(asdict(self.config))) != json.loads(repo_config.read_text()):
            raise ValueError("Frozen configuration mismatch")

    def run(self, entry, case, prices, start=1, initial=None, cash=0, value=None):
        planner, season = self.planner, self.season
        state = planner.clone_state(initial) if initial is not None else season.ReplayState({
            int(pid): season.OwnedPlayer(int(pid), p) for pid, p in case["purchases"].items()
        }, case["bank"], free_transfers=1)
        state.bank += cash
        if start == 1 and initial is None and (
                state.bank < 0 or capital(state, prices[1]) != case["budget"] + cash or
                any(p.purchase_price != prices[1][pid] for pid, p in state.squad.items())):
            raise ValueError("Starting cohort must buy at the recorded GW1 prices")
        wildcards = case["wildcards"]
        split = 19 if entry["season"] == "2025-26" else entry.get("wildcard_first_half_end", 19)
        if (any(not 2 <= g <= 38 for g in wildcards) or len(set(wildcards)) != len(wildcards) or
                len({g <= split for g in wildcards}) != len(wildcards)):
            raise ValueError("Invalid Wildcard schedule")
        trace, snapshots = [], {}
        for gw in range(start, 39):
            forecast, actual = entry["rows"][gw]
            meta, origin = self.project(forecast)
            if not planner.valid_squad(meta, state.squad):
                raise ValueError(f"GW{gw}: roster needs explicit legalisation or player market data")
            if gw in entry["ft_topup_gws"]:
                state.free_transfers = 5
            snapshots[gw] = planner.clone_state(state)
            count = hits = 0
            projected = projected_delta = capital_bonus = None
            with self.scoring(forecast) as scorer:
                if gw in wildcards:
                    wc = self.wildcard.compare_wc_as_ts_action(state, meta, origin, gw, self.config)
                    state, count = wc.state, wc.transfers
                elif gw > 1:
                    boundary = forecast["gws"][-1] + 1
                    bonus = value(boundary, state, gw) if value and boundary <= 38 else None
                    with add_terminal_value(planner, len(forecast["gws"]), bonus):
                        plan = planner.plan_transfer_path(state, meta, origin, gw, self.config)
                    projected = plan.first_action.projected_manager_score
                    if bonus is not None:
                        control = planner.plan_transfer_path(state, meta, origin, gw, self.config)
                        projected_delta = (projected - plan.first_action.official_hit_points
                                           - control.first_action.projected_manager_score
                                           + control.first_action.official_hit_points)
                        explicit_score = sum(weight * action.projected_manager_score
                                             - action.official_hit_points - action.uncertainty_penalty
                                             for weight, action in zip(plan.weights, plan.path))
                        capital_bonus = plan.objective - explicit_score
                    hits, count = plan.first_action.official_hit_points, plan.first_action.transfers
                    planner.execute_first_action(state, plan, meta)
                lineup = scorer.plan(origin, state.squad, gw)
                points, _ = season.actual_team_points(lineup.rows, actual, None, hits)
            self.scorer.decision.cache_clear()
            trace.append(dict(gw=gw, points=points, hits=hits, transfers=count, bank=state.bank,
                              liquidation=capital(state, prices[gw]), projected=projected,
                              same_state_gw_net_xpts_delta=projected_delta, terminal_capital_bonus=capital_bonus,
                              market=state.bank + sum(prices[gw][pid] for pid in state.squad)))
        return trace, snapshots


def net(rows):
    return sum(r["points"] for r in rows)


def estimate(shocks, gw, liquid, wc, step):
    """Average the closest budget match in each earlier season, same GW/chip status."""
    matches = [r for r in shocks if (r["gw"], r["wc"], r["step"]) == (gw, wc, step)]
    if not matches:
        return None
    values = []
    for season in sorted({r["season"] for r in matches}):
        rows = [r for r in matches if r["season"] == season]
        distance = min(abs(r["liquid"] - liquid) for r in rows)
        values.append(np.mean([r["slope"] for r in rows if abs(r["liquid"] - liquid) == distance]))
    return float(np.mean(values))


def metrics(trace):
    return dict(points=net(trace), liquidation=trace[-1]["liquidation"], market=trace[-1]["market"],
                bank=float(np.mean([r["bank"] for r in trace])),
                transfers=sum(r["transfers"] for r in trace),
                weekly_points_variance=float(np.var([r["points"] for r in trace], ddof=1)))


def interval(season_deltas):
    rng = np.random.default_rng(20261128)
    draws = rng.choice(season_deltas, size=(10000, len(season_deltas)), replace=True).mean(axis=1)
    return np.quantile(draws, [.025, .975]).tolist()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--frozen", required=True, type=Path)
    cli.add_argument("--manifest", required=True, type=Path)
    cli.add_argument("--out", required=True, type=Path)
    args = cli.parse_args()
    replay = Replay(args.frozen.resolve())
    seasons, holdout = load_data(args.manifest, replay.validate)
    args.out.mkdir(parents=True, exist_ok=False)
    shocks, training, outcomes = [], [], []
    for entry in seasons:
        name = entry["season"]
        prices, samples = price_maps(entry), price_samples(training)
        for case in entry["cases"]:
            baseline, states = replay.run(entry, case, prices)
            report = dict(season=name, case=case["id"], baseline=metrics(baseline), trace=baseline)
            if training:
                for step in (1, 5):
                    def value(boundary, state, gw):
                        coefficient = estimate(shocks, boundary, capital(state, prices[gw]),
                                               boundary in case["wildcards"], step)
                        if coefficient is None or coefficient == 0:
                            return None
                        positions = {p["id"]: p["position"] for p in entry["rows"][gw][0]["players"]}
                        return terminal_bonus(samples, coefficient, prices[gw], prices[gw-1],
                                              positions, boundary - gw)
                    trace, _ = replay.run(entry, case, prices, value=value)
                    report[f"empirical_{step}"] = dict(metrics=metrics(trace), trace=trace)
            outcomes.append(report)
            if name in holdout:
                continue
            for gw in sorted(set(MEASUREMENT_WEEKS) | set(range(8, 39))):
                for step in (1, 5):
                    bumped, _ = replay.run(entry, case, prices, start=gw, initial=states[gw], cash=step)
                    shocks.append(dict(season=name, case=case["id"], gw=gw, step=step,
                                       liquid=capital(states[gw], prices[gw]), wc=gw in case["wildcards"],
                                       slope=10 * (net(bumped) - net(baseline[gw-1:])) / step))
        if name not in holdout:
            training.append(entry)
    summary = {}
    for step in (1, 5):
        deltas = [np.mean([r[f"empirical_{step}"]["metrics"]["points"] - r["baseline"]["points"]
                           for r in outcomes if r["season"] == name]) for name in holdout]
        summary[str(step)] = dict(mean=float(np.mean(deltas)), season_deltas=deltas, ci95=interval(deltas))
    measured = []
    for gw in MEASUREMENT_WEEKS:
        for step in (1, 5):
            for wc in (False, True):
                bucket = [r for r in shocks if (r["gw"], r["step"], r["wc"]) == (gw, step, wc)]
                means = [float(np.mean([r["slope"] for r in bucket if r["season"] == name]))
                         for name in sorted({r["season"] for r in bucket})]
                if means:
                    measured.append(dict(gw=gw, step=step, wildcard=wc, seasons=len(means),
                                         pts_per_million=float(np.mean(means)),
                                         ci95=interval(means) if len(means) >= 2 else None))
    result = dict(frozen=PIN, manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                  holdout=holdout, outcomes=outcomes, calibration=shocks, measured=measured, summary=summary)
    (args.out / "replay.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
