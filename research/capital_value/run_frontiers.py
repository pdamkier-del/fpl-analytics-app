"""Reproduce the observed-origin budget curves and their figure."""
import argparse
import csv
import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path

from frontier import Player, global_squad, local_options, local_squad, sale_price

SOURCES = {
    12: ("f54f651ea03ee099ef5be35c9cb36eddc3a8472470ead2aaac786b097c281633",
         "0f3bc1aa31d183d6a0dcb96e5b4b3a0d306e89342a2654460a26bfbb9d59de94",
         "2026-11-23T08:16:49Z"),
    13: ("98e2e695da6e7651f3c2a015f8540e27ecd5ca8b0e22abab6270d2d56126e66e",
         "308e9426df3d2b2376c9f10f5cd6850b45b7f33fb660b87168cbaa27f263869a",
         "2026-11-28T11:00:08Z"),
}


def load(path, gw):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCES[gw][1]:
        raise ValueError(f"Unexpected forecast bytes for GW{gw}")
    data = json.loads(gzip.decompress(raw))
    if (data["gws"][0] != gw or data["season"] != "2026-27" or
            not datetime.fromisoformat(data["data_asof"]) <= datetime.fromisoformat(SOURCES[gw][2])
            <= datetime.fromisoformat(data["origin_deadline"])):
        raise ValueError("Forecast vintage mismatch")
    return [Player(p["id"], p["position"], p["team_id"], p["price_tenths"],
                   next(w["xpts"] for w in p["weeks"] if w["gw"] == gw))
            for p in data["players"]]


def sweep(rows, gw, label, budgets, solve, market):
    previous = None
    for budget in budgets:
        optimal = solve(budget)
        if optimal is None:
            previous = None
            continue
        if previous and optimal.points < previous.points - 1e-6:
            raise RuntimeError("Non-monotone frontier")
        slope = round(10 * (optimal.points - previous.points), 9) if previous else None
        rows.append([gw, label, budget, optimal.points, slope, optimal.cost,
                     sum(market[p] for p in optimal.ids), *optimal.spending,
                     " ".join(map(str, optimal.ids))])
        previous = optimal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    rows, squads = [], {}
    for gw in SOURCES:
        players = load(args.input / f"gw{gw}" / "forecast.json.gz", gw)
        market = {p.id: p.price for p in players}
        global_solutions = {b: global_squad(players, b, market) for b in range(820, 1021)}
        sweep(rows, gw, "global", global_solutions, global_solutions.get, market)
        if not squads:
            for b in (980, 1000, 1020):
                winner = global_solutions[b]
                squads[b] = {p: market[p] for p in winner.ids}, b - winner.cost
        for b, (purchase, bank) in squads.items():
            nominal = bank + sum(market[p] for p in purchase)
            liquidation = bank + sum(sale_price(cost, market[p]) for p, cost in purchase.items())
            costs, options = local_options(players, purchase)
            budgets = range(liquidation, liquidation + 11)
            for position, label in enumerate(("local", "GKP", "DEF", "MID", "FWD")):
                sweep(rows, gw, f"{label}-{b}", budgets,
                      lambda budget: local_squad(options, budget, position or None), market)
            sweep(rows, gw, f"wildcard-{b}", budgets,
                  lambda budget: global_squad(players, budget, costs), market)
            zero_bank = liquidation - bank
            for position, label in enumerate(("local", "GKP", "DEF", "MID", "FWD")):
                sweep(rows, gw, f"{label}-zero-bank-{b}", range(zero_bank, zero_bank + 11),
                      lambda budget: local_squad(options, budget, position or None), market)
            sweep(rows, gw, f"wildcard-zero-bank-{b}", range(zero_bank, zero_bank + 11),
                  lambda budget: global_squad(players, budget, costs), market)
            print(gw, b, nominal, liquidation, flush=True)
    with (args.out / "frontiers.csv").open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["gw", "scope", "budget_tenths", "xpts", "slope_pts_per_million_at_previous_budget",
                         "opportunity_cost_tenths", "squad_market_tenths", "gkp", "def", "mid", "fwd", "ids"])
        writer.writerows(rows)

    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(10, 6), layout="constrained")
    for i, gw in enumerate(SOURCES):
        for label, title in (("global", "Frit trupvalg"), ("local-1000", "Op til én transfer"),
                             ("wildcard-1000", "Wildcard fra samme trup"),
                             ("local-zero-bank-1000", "Én transfer, tom bank")):
            group = [r for r in rows if r[:2] == [gw, label]]
            line, = axes[0, i].step([r[2] / 10 for r in group], [r[3] for r in group],
                                    where="post", label=title)
            axes[1, i].plot([(r[2] - 1) / 10 for r in group[1:]], [r[4] for r in group[1:]],
                            ".-", ms=3, color=line.get_color())
        axes[0, i].set(title=f"GW{gw}", ylabel="Forventede GW-point")
        axes[1, i].set(xlabel="Budget (£m)", ylabel="Marginale GW-point pr. £m")
    axes[0, 0].legend(fontsize=8)
    fig.savefig(args.out / "frontiers.png", dpi=160)


if __name__ == "__main__":
    main()
