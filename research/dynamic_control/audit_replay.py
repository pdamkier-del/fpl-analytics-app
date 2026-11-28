"""Post-decision ledger audit, paired decision diagnostics and TC overlay."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ARMS = ("tsv3", "equal6", "mpc10", "terminal8")


def player_ids(field):
    return tuple(int(pid) for pid in str(field).split(";") if pid)


def bootstrap(delta, length=4):
    """Circular paired block resampling as sensitivity within the same season."""
    rng = np.random.default_rng(20261128)
    starts = rng.integers(len(delta), size=(3000, (len(delta) + length - 1) // length))
    indexes = ((starts[:, :, None] + np.arange(length)) % len(delta)).reshape(3000, -1)
    totals = np.array(delta)[indexes[:, :len(delta)]].sum(axis=1)
    return list(map(float, np.percentile(totals, [5, 95])))


def audit(source, results):
    sys.path[:0] = [str(source / "scripts"), str(source / "src")]
    import run_transfer_strategy_v3_replay as legacy
    import run_horizon_policy_comparison as hp
    from fpl_xpts.optimize import plan_squad
    from fpl_xpts.season_replay import actual_team_points, selling_price, valid_squad

    outcomes, names, forecasts = legacy.prepare()
    known = hp.gw_meta(outcomes, names, 1)
    seeds = [json.loads((results / f"{arm}.json").read_text()) for arm in ARMS]
    if any((s["initial"], s["bank"], s["free_transfers"], s["sha256"]) !=
           (seeds[0]["initial"], seeds[0]["bank"], seeds[0]["free_transfers"], seeds[0]["sha256"])
           for s in seeds):
        raise ValueError("Arms have different seeds or source files")
    weekly = []
    for arm, seed in zip(ARMS, seeds, strict=True):
        ledger = pd.read_csv(results / f"{arm}.csv", keep_default_na=False)
        if ledger.gw.tolist() != list(range(1, 39)):
            raise ValueError(f"Incomplete historical arm {arm}")
        bank, ft = seed["bank"], seed["free_transfers"]
        owned = {int(pid): price for pid, price in seed["initial"].items()}
        last_buy = {}
        meta = known.copy()
        tc_used = False
        for row in ledger.itertuples():
            gw = row.gw
            incoming, outgoing = player_ids(row.incoming), player_ids(row.outgoing)
            if gw > 2:
                observed = hp.gw_meta(outcomes, names, gw - 1)
                meta = pd.concat([meta[~meta.id.isin(observed.id)], observed], ignore_index=True)
            current = hp.complete_current_projection(forecasts[forecasts.origin_gw.eq(gw - 1)], meta, gw)
            actual = hp.actual_gw(outcomes, gw)
            hold = plan_squad(current, list(owned), gw)
            hold_score, _ = actual_team_points(hold.rows, actual, None, 0)
            prices = meta.set_index("id").price_tenths.to_dict()
            short_holds = sum(0 < gw - last_buy.get(pid, -39) <= 3 for pid in outgoing)
            if row.transfers != len(incoming) or len(incoming) != len(outgoing) or row.transfers > 5:
                raise ValueError(f"Invalid transfer count {arm} GW{gw}")
            # Forced repairs execute in order before the optional simultaneous bundle.
            for out_id, in_id in zip(outgoing[:row.forced], incoming[:row.forced], strict=True):
                bank += selling_price(owned.pop(out_id), prices[out_id]) - prices[in_id]
                owned[in_id] = prices[in_id]
                last_buy[in_id] = gw
            for pid in outgoing[row.forced:]:
                bank += selling_price(owned.pop(pid), prices[pid])
            for pid in sorted(incoming[row.forced:]):
                bank -= prices[pid]
                owned[pid] = prices[pid]
                last_buy[pid] = gw
            hits = 4 * max(0, row.transfers - ft)
            if row.ft_before != ft or hits != row.hits:
                raise ValueError(f"Invalid transfer cost {arm} GW{gw}")
            ft = min(5, max(0, ft - row.transfers) + 1)
            if ft != row.ft_after or bank != row.bank or bank < 0 or not valid_squad(meta, owned):
                raise ValueError(f"Invalid transition {arm} GW{gw}")
            plan = plan_squad(current, list(owned), gw)
            if int(plan.rows.loc[plan.rows.role.eq("C"), "id"].iloc[0]) != row.captain:
                raise ValueError(f"Captain disagreement {arm} GW{gw}")
            score, _ = actual_team_points(plan.rows, actual, None, hits)
            if score != row.points:
                raise ValueError(f"Score disagreement {arm} GW{gw}")
            tc_gain = 0
            fixtures = current.loc[current.id.eq(row.captain), "fixtures"].max()
            played_tc = not tc_used and gw >= 20 and (fixtures >= 2 or gw == 38)
            if played_tc:
                tc_used = True
                tc_score, _ = actual_team_points(plan.rows, actual, "triple_captain", hits)
                tc_gain = tc_score - score
            weekly.append(dict(arm=arm, gw=gw, points=score, hold_points=hold_score,
                               same_state_gain=score - hold_score if not row.forced else np.nan,
                               same_state_expected_gain=plan.expected_score - hits - hold.expected_score
                               if not row.forced else np.nan, transfers=row.transfers, hits=hits,
                               rolls=int(row.transfers == 0), short_holds=short_holds,
                               tc_gain=tc_gain, tc=played_tc, seconds=row.seconds,
                               ft_before=row.ft_before, ft_after=row.ft_after, bank=row.bank))
    weekly = pd.DataFrame(weekly)
    weekly.to_csv(results / "historical-weekly.csv", index=False)
    baseline = weekly[weekly.arm.eq("tsv3")].points.to_numpy()
    summary = []
    for arm in ARMS:
        data = weekly[weekly.arm.eq(arm)]
        delta = data.points.to_numpy() - baseline
        summary.append(dict(arm=arm, points=int(data.points.sum()), delta=int(delta.sum()),
                            gw01_19=int(data.points.iloc[:19].sum()),
                            gw20_38=int(data.points.iloc[19:].sum()),
                            paired_block_p05_p95=bootstrap(delta),
                            leave_one_gw_out=[int(delta.sum() - max(delta)), int(delta.sum() - min(delta))],
                            transfers=int(data.transfers.sum()), hits=int(data.hits.sum()),
                            rolls=int(data.rolls.sum()), short_holds=int(data.short_holds.sum()),
                            same_state_gain=int(data.same_state_gain.sum()),
                            same_state_expected_gain=float(data.same_state_expected_gain.sum()),
                            tc_gw=int(data.loc[data.tc, "gw"].iloc[0]),
                            tc_gain=int(data.tc_gain.sum()), points_with_tc=int((data.points + data.tc_gain).sum()),
                            seconds=float(data.seconds.sum()),
                            median_seconds=float(data.seconds.median())))
    (results / "historical-summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    audit(args.source.resolve(), args.results)
