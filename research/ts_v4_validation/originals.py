"""Compare the fixed shortlist on two retained original MM/PM issues."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

from compare import ARMS, check_pin, fixed_proposer, variant

C1 = "a07e8f7aef0e9bdc9e5dfbb6a31f157c37826af9"
PR65 = "3715a063e6b9e8e3458205331b5f844703c6781b"
FROZEN = "161b67b6fb8786a38e78c245b92a03ad841575d8"
REVISIONS = (
    "f54f651ea03ee099ef5be35c9cb36eddc3a8472470ead2aaac786b097c281633",
    "98e2e695da6e7651f3c2a015f8540e27ecd5ca8b0e22abab6270d2d56126e66e",
)
MARKET_GW12 = "9e03db632b5297c24238e55002baa9992156f9006e510993adc6d501552f2a41"
TOLERANCE = .25


def market_vintage(inputs, cutoff):
    import pandas as pd
    from data import daily
    from fetch import read_json
    import models

    panel, _, _ = daily(inputs, read_json(inputs / "cache-selection.json")["daily"])
    observed = panel[(panel.season == "2026-27") & panel.time.le(cutoff)].time.max()
    if pd.isna(observed) or (cutoff - observed) > pd.Timedelta(hours=24):
        return observed, None
    fold_slices = models.slices

    def one_fold(*args, **kwargs):
        for train, test in fold_slices(*args, **kwargs):
            if test.time.eq(observed).any():
                yield train, test

    with patch.object(models, "slices", one_fold):
        scores = models.price_forecasts(panel, 3, "daily")
    scores = scores[(scores.time == observed) & (scores.model == "boost_full")].set_index("player")
    prices = panel[panel.time.eq(observed)].set_index("player").price
    return observed, scores.join(prices)


def expected_edge(scores, prices, purchases, action, sale_price):
    """Rolling minus transferring, in expected £0.1m liquidation units."""
    ids = set(action.outgoing) | set(action.incoming)
    if scores is None or not ids.issubset(scores.index):
        return None
    if any(scores.loc[pid, "price"] != prices[pid] for pid in ids):
        return None

    def change(pid, paid):
        px = prices[pid]
        return sum(scores.loc[pid, prob] * (sale_price(paid, px + tick) - sale_price(paid, px))
                   for prob, tick in (("p_fall", -1), ("p_rise", 1)))

    return sum(change(pid, purchases[pid]) for pid in action.outgoing) - sum(
        change(pid, prices[pid]) for pid in action.incoming)


def market_decision(gap, edge, point_hits, roll_hits, point_transfers):
    if not point_transfers:
        return "already_roll"
    if not -1e-8 <= gap <= TOLERANCE:
        return "outside_near_tie"
    if roll_hits > point_hits:
        return "extra_hits_excluded"
    if edge is None:
        return "blocked_market_vintage"
    return "switch_to_roll" if edge > 0 else "keep_point_action"


def plan_set(planner, state, meta, origin, gw, config, arms):
    results = {}
    for arm in arms:
        started = perf_counter()
        with fixed_proposer(planner, gw, config.weights):
            results[arm] = (planner.plan_transfer_path(
                state, meta, origin, gw, variant(config, arm)), perf_counter() - started)
    proposer = planner._fast_local_candidate_squads

    def first_roll(node, meta, origin, gws, *args):
        return [] if gws[0] == gw else proposer(node, meta, origin, gws, *args)

    started = perf_counter()
    with patch.object(planner, "_fast_local_candidate_squads", first_roll):
        result = planner.plan_transfer_path(state, meta, origin, gw, config)
    results["force_roll"] = (result, perf_counter() - started)
    return results


def run(c1, frozen, market, inputs, releases, output, revisions):
    import pandas as pd

    sys.path.insert(0, str(c1 / "research/ts_search/code"))
    from run_experiment import load_frozen
    planner, season, scoring, live, config, _ = load_frozen(frozen)
    sys.path[:0] = [str(Path(__file__).resolve().parents[2] / "integration/research-data"),
                    str(market / "research/market_dynamics")]
    from archive import verify
    from fetch import read_json
    from worker import audit as audit_nomination

    case = read_json(c1 / "research/results/EXP-TS-FUNDING-REALPOOL-001/v2-attempt/states/01.json")
    rows = []
    for revision in revisions:
        folder = releases / revision
        manifest = verify(folder)
        proof = read_json(releases / f"{revision}.proof.json")
        forecast = read_json(folder / "forecast.json.gz")
        gw = forecast["gws"][0]
        assert manifest["revision_id"] == proof["revision_id"] == revision
        assert pd.Timestamp(manifest["data_cutoff"]) <= pd.Timestamp(proof["publication_at"]) < pd.Timestamp(
            manifest["official_deadline"])
        assert json.loads(json.dumps(asdict(config))) == read_json(folder / "ts-config.json")
        meta, origin = live.project(forecast)
        purchases = {int(pid): cost for pid, cost in case["purchase_prices"].items()}
        state = season.ReplayState({pid: season.OwnedPlayer(pid, cost) for pid, cost in purchases.items()},
                                   case["bank"], case["free_transfers"])
        before = asdict(state)
        players = {row["id"]: row for row in forecast["players"]}
        prices = {pid: row["price_tenths"] for pid, row in players.items()}
        official = read_json(folder / "official-bootstrap.json.gz")
        official_prices = {row["id"]: row["now_cost"] for row in official["elements"]}
        if any(official_prices.get(pid) != price for pid, price in prices.items()):
            raise ValueError(f"Forecast and official prices disagree for GW{gw}")
        assert planner.valid_squad(meta, state.squad)
        with scoring.preview_scoring(forecast) as scorer:
            arms = ["tsv3"] if revision == MARKET_GW12 else list(ARMS)[:5]
            policies = plan_set(planner, state, meta, origin, gw, config, arms)
            for arm, (result, seconds) in policies.items():
                assert asdict(state) == before and tuple(result.horizon_gws) == tuple(forecast["gws"])
                audit_path(planner, case, result, players, meta, scorer, forecast,
                           audit_nomination, config)
                print(gw, arm, round(seconds, 2), flush=True)
        base, roll = (policies[name][0] for name in ("tsv3", "force_roll"))
        assert roll.path[0].transfers == roll.path[0].official_hit_points == 0
        quote, market_scores = market_vintage(inputs, pd.Timestamp(manifest["data_cutoff"]))
        gap = base.objective - roll.objective
        edge = expected_edge(market_scores, prices, purchases, base.path[0], season.selling_price)
        decision = market_decision(gap, edge, base.path[0].official_hit_points, 0, base.path[0].transfers)
        rows.append({
            "gw": gw, "revision": revision, "forecast_sha256": manifest["forecast_sha256"],
            "cutoff": manifest["data_cutoff"], "publication": proof["publication_at"],
            "deadline": manifest["official_deadline"], "market_observed_at": str(quote),
            "usable_market_fold": market_scores is not None,
            "scenario_draws": forecast["scenario_contract"]["draws"],
            "player_count": len(players), "state_before": before, "roll_gap": gap,
            "roll_market_edge_tenths": edge, "market_decision": decision,
            "arms": {arm: dict(seconds=seconds, objective=result.objective, path=[asdict(a) for a in result.path])
                     for arm, (result, seconds) in policies.items()},
        })
        ordered = sorted(rows, key=lambda row: (row["gw"], row["publication"]))
        output.write_text(json.dumps(ordered, indent=2) + "\n")


def audit_path(planner, case, result, players, meta, scorer, forecast, audit_nomination, config):
    from reference import transition

    purchases = tuple(sorted((int(pid), cost) for pid, cost in case["purchase_prices"].items()))
    bank, ft, objective = case["bank"], case["free_transfers"], 0.
    source = {pid: dict(position=p["position"], team=p["team_id"], price=p["price_tenths"])
              for pid, p in players.items()}
    for action, weight in zip(result.path, result.weights, strict=True):
        ids = tuple(sorted((set(dict(purchases)) - set(action.outgoing)) | set(action.incoming)))
        assert planner.valid_squad(meta, set(ids))
        after, outgoing, incoming, hits, paid = transition(purchases, bank, ft, ids, source)
        assert (action.outgoing, action.incoming, action.official_hit_points) == (outgoing, incoming, hits)
        assert (action.bank_before, action.bank_after) == (bank, after[1])
        assert (action.free_transfers_before, action.free_transfers_after) == (ft, after[2])
        assert abs(action.uncertainty_penalty - paid * config.hit_uncertainty_buffer) < 1e-8
        score = audit_nomination(ids, action.gw, scorer, source, forecast)[-1]
        assert abs(action.projected_manager_score - score) < 1e-8
        objective += weight * score - hits - action.uncertainty_penalty
        purchases, bank, ft = after
    assert abs(result.objective - objective) < 1e-8


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("c1", "frozen", "market", "inputs", "releases", "output"):
        parser.add_argument(key, type=Path)
    parser.add_argument("--revision", choices=(*REVISIONS, MARKET_GW12))
    args = parser.parse_args()
    for path, pin in [(args.c1, C1), (args.frozen, FROZEN), (args.market, PR65)]:
        check_pin(path, pin)
    sys.path.insert(0, str(args.c1 / "research/ts_realpool"))
    revisions = (args.revision,) if args.revision else (*REVISIONS, MARKET_GW12)
    run(args.c1, args.frozen, args.market, args.inputs, args.releases, args.output, revisions)
