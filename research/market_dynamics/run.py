"""Run the isolated FPL market study and write reproducible research evidence."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from threadpoolctl import threadpool_limits

from data import daily, weekly
from dynamics import dynamics_metrics
from fetch import read_json
from models import price_forecasts, price_metrics, sports_forecasts, sports_metrics
from original import current_finality, diagnostic_inventory, frozen_scores, release_inventory
from replay import season_replay


def write_json(data, output):
    output.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def label_graph(ax, title, xlabel, ylabel):
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(alpha=.2)


def figures(output, calibration, dynamics, policy):
    colors = {"climatology": "#718096", "logit_flow": "#d27629",
              "logit_l2_full": "#126c80", "boost_full": "#6c4a9a"}
    names = {"climatology": "Historisk frekvens", "logit_flow": "Logit med flow",
             "logit_l2_full": "L2-logit", "boost_full": "Boosting"}
    panel = calibration[(calibration.scope == "all")
                        & calibration.model.isin(colors) & calibration["class"].ne("flat")]
    windows = [("daily", 1), ("daily", 3), ("weekly", 1), ("weekly", 2)]
    fig, axes = plt.subplots(2, 4, figsize=(13, 6), sharex=True, sharey=True)
    for ix, (frequency, horizon) in enumerate(windows):
        for jx, (cls, text) in enumerate([("rise", "Stigning"), ("fall", "Fald")]):
            ax = axes[jx, ix]
            sample = panel[(panel.frequency == frequency) & (panel.horizon == horizon)
                           & (panel["class"] == cls)]
            for arm, rows in sample.groupby("model"):
                rows = rows[rows.n >= 20]
                ax.plot(rows.predicted, rows.observed, marker="o", markersize=3,
                        label=names[arm], color=colors[arm])
            ax.plot([0, 1], [0, 1], ":", color="#555")
            unit = ("dag" if horizon == 1 else "dage") if frequency == "daily" else "GW"
            label_graph(ax, f"{text} · {horizon} {unit}",
                        "Forudsagt sandsynlighed" if jx else "",
                        "Observeret frekvens" if ix == 0 else "")
            ax.set(xlim=(0, 1), ylim=(0, 1))
            ax.set_xscale("symlog", linthresh=.01)
            ax.set_yscale("symlog", linthresh=.01)
            ticks = [0, .01, .05, .2, 1]
            percentages = ["0 %", "1 %", "5 %", "20 %", "100 %"]
            ax.set_xticks(ticks, percentages)
            ax.set_yticks(ticks, percentages)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False)
    fig.tight_layout(rect=(0, .07, 1, 1))
    fig.savefig(output / "kalibrering.png", dpi=150)
    plt.close(fig)

    corr = pd.DataFrame(dynamics["correlations"])
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    axes_pairs = [("weekly", "Forskydning i GW"), ("daily", "Forskydning i dage")]
    for ax, (freq, xlabel) in zip(axes, axes_pairs):
        cohort = corr[corr.frequency == freq]
        for (source, target), (name, color) in {
            ("flow", "last_price_change_other"): ("Flow → prisændring", "#126c80"),
            ("flow", "flow_other"): ("Flow → flow", "#d27629"),
            ("points", "flow_other"): ("Faktiske point → flow", "#40844d"),
            ("acceleration", "last_price_change_other"): ("Flowacceleration → prisændring", "#a24b58"),
        }.items():
            line = cohort[(cohort.x == source) & (cohort.y == target)]
            if line.empty:
                continue
            bounds = pd.DataFrame(line.ci95.to_list(), index=line.offset).reindex(range(-2, 3))
            means = line.set_index("offset")["mean"].reindex(bounds.index)
            ax.plot(means.index, means, "o-", markersize=3, label=name, color=color)
            ax.fill_between(bounds.index, bounds[0], bounds[1], alpha=.12, color=color)
        ax.axhline(0, lw=.8, color="#777")
        ax.set_xticks(range(-2, 3))
        label_graph(ax, "GW-observationer" if freq == "weekly" else "Dagsobservationer",
                    xlabel, "Rangkorrelation" if freq == "weekly" else "")
    axes[0].legend(loc="best", frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(output / "lead-lag.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    paired = policy.pivot(index="season", columns="arm", values="paired_delta")
    paired[["market_points", "price_aware"]].rename(columns={
        "market_points": "Pointproxy med marked", "price_aware": "Pointproxy med prisprognose"
    }).plot.bar(ax=ax, color=["#126c80", "#d27629"], rot=0)
    ax.axhline(0, lw=.8, color="#777")
    ax.legend(frameon=False)
    label_graph(ax, "Sæsonreplay med højst én transfer pr. GW", "Sæson",
                "Pointforskel mod samme reference")
    fig.tight_layout()
    fig.savefig(output / "saesonpoint.png", dpi=150)
    plt.close(fig)


def run(root, output):
    output.mkdir(parents=True, exist_ok=True)
    receipt = read_json(root / "cache-selection.json")
    weekly_panel, weekly_audit, weekly_inventory = weekly(root, receipt["weekly"], receipt["terminal"])
    daily_panel, daily_audit, daily_inventory = daily(root, receipt["daily"])
    sources = Path(__file__).resolve().parents[2] / "analysis/audits/2026-11-22/inputs/archive"
    # from research/market_dynamics/run.py, parents[2] is the repository root
    frozen_coverage, frozen = frozen_scores(root, daily_panel, sources)
    frozen.to_csv(output / "frozen_mm_pm.csv", index=False, float_format="%.9g")
    write_json({
        "weekly": weekly_audit, "daily": daily_audit, "weekly_vintages": weekly_inventory,
        "daily_vintages": daily_inventory, "frozen_join": frozen_coverage,
        "current_season_label_finality": current_finality(root),
        "forecast_releases": release_inventory(root), "diagnostic_archive": diagnostic_inventory(root),
    }, output / "data_audit.json")
    dynamics = dynamics_metrics(weekly_panel, daily_panel)
    write_json(dynamics, output / "dynamics.json")

    metrics, calibration = [], []
    with threadpool_limits(limits=2):
        for frequency, panel, horizons, width in [("weekly", weekly_panel, [1, 2], 4),
                                                   ("daily", daily_panel, [1, 3], 7)]:
            for horizon in horizons:
                print(f"Walk-forward {frequency} +{horizon}", flush=True)
                predictions = price_forecasts(panel, horizon, frequency)
                scores, bins = price_metrics(predictions, width)
                metrics.append(scores.assign(frequency=frequency, horizon=horizon))
                calibration.append(bins.assign(frequency=frequency, horizon=horizon))
                if frequency == "weekly" and horizon == 1:
                    policy_prices = predictions
        sports = sports_forecasts(weekly_panel)
    scores = pd.concat(metrics, ignore_index=True)
    bins = pd.concat(calibration, ignore_index=True)
    scores.to_csv(output / "price_metrics.csv", index=False, float_format="%.9g")
    bins.to_csv(output / "calibration.csv", index=False, float_format="%.9g")
    write_json(sports_metrics(sports), output / "sports.json")

    ledger, policy = season_replay(weekly_panel, sports, policy_prices)
    ledger.to_csv(output / "replay_weeks.csv", index=False, float_format="%.9g")
    policy.to_csv(output / "replay_summary.csv", index=False, float_format="%.9g")
    figures(output, bins, dynamics, policy)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs, args.output)
