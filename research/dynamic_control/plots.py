"""Render research figures from committed run outputs."""
import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot(results, exact_only=False):
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                         "figure.dpi": 160, "savefig.bbox": "tight"})
    exact = pd.DataFrame(json.loads((results / "exact.json").read_text()))
    matrix = exact.pivot(index="case", columns="method", values="gap")
    matrix = matrix[["greedy", "rho060", "mpc2", "beam1", "beam8", "terminal", "mcts512"]]
    fig, ax = plt.subplots(figsize=(9, 4))
    shown = ax.imshow(matrix, cmap="Blues", aspect="auto", vmin=0)
    ax.set_xticks(range(len(matrix.columns)), matrix.columns)
    ax.set_yticks(range(len(matrix)), [label.replace("_", " ") for label in matrix.index])
    ax.set_title("Eksakt forventet pointtab ved det første valg")
    for (row, col), gap in np.ndenumerate(matrix.to_numpy()):
        ax.text(col, row, f"{gap:.1f}", va="center", ha="center",
                color="white" if gap > 0.6 * matrix.max().max() else "#111827")
    fig.colorbar(shown, ax=ax, label="Point")
    fig.savefig(results / "exact-gaps.png")
    plt.close(fig)

    if exact_only:
        return

    weekly = pd.read_csv(results / "historical-weekly.csv")
    totals = weekly.pivot(index="gw", columns="arm", values="points").cumsum()
    fig, ax = plt.subplots(figsize=(8, 4))
    for arm, label, color in [("equal6", "6 GW, lige vægte", "#117d79"),
                              ("mpc10", "10 GW, forlænget prognose", "#db4c30"),
                              ("terminal8", "6 GW + estimeret fortsættelse", "#5f4ca6")]:
        ax.plot(totals.index, totals[arm] - totals.tsv3, label=label, color=color, lw=2)
    ax.axhline(0, color="#374151", lw=1, ls="--")
    ax.legend(frameon=False)
    ax.set(xlabel="Gameweek", ylabel="Akkumuleret pointforskel",
           title="Historisk proxy · forskel fra TS v3 efter hits")
    fig.savefig(results / "historical-points.png")
    plt.close(fig)


if __name__ == "__main__":
    plot(Path(sys.argv[1]), exact_only="--exact-only" in sys.argv[2:])
