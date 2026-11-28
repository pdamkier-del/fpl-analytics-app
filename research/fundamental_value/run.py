"""Research-only proxy replay. See README.md for data timing and limitations."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import t

SEASONS = ("2022-23", "2023-24", "2024-25")
SLOTS = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
FLOOR = {"GK": 40, "DEF": 40, "MID": 45, "FWD": 45}
MINIMUM = {"GK": 1, "DEF": 3, "MID": 2, "FWD": 1}
FORMATIONS = [(1, d, m, 10-d-m) for d in range(3, 6) for m in range(2, 6)
              if 1 <= 10-d-m <= 3]
SIGNALS = ("gap", "gap_ratio", "ownership", "return_proxy", "new_starter",
           "underlying_gap", "haul", "momentum")


def read_season(path, season):
    players = path / f"{season}.csv"
    fixtures = path / f"fixtures-{season}.csv"
    raw = pd.read_csv(players, low_memory=False)
    raw = raw[raw.position.isin(SLOTS)].copy()
    assert not raw.duplicated(["element", "fixture"]).any()
    assert raw.GW.between(1, 38).all()
    fixture = pd.read_csv(fixtures)
    assert fixture.id.is_unique and set(raw.fixture) <= set(fixture.id)
    mapped = fixture.set_index("id")
    raw["club"] = np.where(raw.was_home, raw.fixture.map(mapped.team_h),
                           raw.fixture.map(mapped.team_a))
    raw["kickoff"] = pd.to_datetime(raw.kickoff_time, utc=True)
    raw["xgi"] = raw.expected_goal_involvements
    assert raw[["kickoff", "value", "selected", "minutes", "total_points", "xgi",
                "starts", "club"]].notna().all().all()
    raw = raw.sort_values(["kickoff", "fixture"])
    weekly = raw.groupby(["GW", "element"]).agg(
        pos=("position", "last"), club=("club", "last"), price=("value", "last"),
        selected=("selected", "last"), minutes=("minutes", "sum"),
        starts=("starts", "sum"), points=("total_points", "sum"),
        xgi=("xgi", "sum"), net=("transfers_balance", "last"),
    )
    audit = {
        "fixture_rows": len(raw), "player_weeks": len(weekly),
        "multi_fixture_weeks": int((raw.groupby(["GW", "element"]).size() > 1).sum()),
        "observed_weeks": int(raw.GW.nunique()),
        "sha256": {file.name: hashlib.sha256(file.read_bytes()).hexdigest()
                   for file in (players, fixtures)},
    }
    return raw, weekly, fixture, audit


def snapshot(raw, fixtures, gw, horizon, final_schedule=False):
    # Even overlapping GW labels cannot expose a late fixture's realised stats.
    # The conservative five-day buffer precedes the first kickoff.
    first = raw.loc[raw.GW.eq(gw), "kickoff"].min()
    history = raw[(raw.GW <= gw-2) &
                  (raw.kickoff < first - pd.Timedelta(days=5))]
    history = history.sort_values(["GW", "kickoff", "fixture"])
    latest = history.drop_duplicates("element", keep="last").set_index("element")
    latest = latest[latest.GW >= gw-5]
    recent = history[(history.GW >= gw-6)]
    prior = history[(history.GW >= gw-12) & (history.GW < gw-6)]
    data = latest[["position", "club", "value", "selected", "transfers_balance", "GW"]].copy()
    data.columns = ["pos", "club", "price", "selected", "net", "vintage"]
    data["ownership"] = np.log1p(data.selected)
    data["momentum"] = data.net / (data.selected + 10000)
    agg = recent.groupby("element").agg(minutes=("minutes", "sum"), starts=("starts", "sum"),
                                         points=("total_points", "sum"), xgi=("xgi", "sum"),
                                         n=("minutes", "size"), variance=("minutes", "std"))
    data = data.join(agg)
    data["xm"] = (data.minutes.fillna(0) + 90) / (data.n.fillna(0) + 2)
    data["uncertainty"] = data.variance.fillna(45) / 90
    role = recent.groupby("element").tail(2).groupby("element").starts.mean()
    old = prior.groupby("element").minutes.mean()
    recent_starts = data.starts.fillna(0) / data.n.fillna(1)
    data["new_starter"] = (role.ge(1) & recent_starts.le(0.5)).astype(float)
    data["return_proxy"] = (role.ge(0.5) & old.ge(55) & data.minutes.le(180)).astype(float)
    expected_attacking = data.xgi.fillna(0) * data.pos.map(
        {"GK": 5, "DEF": 5, "MID": 4, "FWD": 4})
    data["underlying_gap"] = (expected_attacking -
                              recent.assign(real=recent.goals_scored*4+recent.assists*3)
                              .groupby("element").real.sum().reindex(data.index).fillna(0)
                              ) / data.n.fillna(1)
    data["haul"] = latest.total_points.ge(10).astype(float)
    residual = recent.total_points - recent.minutes.ge(60).astype(int) - recent.minutes.gt(0)
    residual -= recent.xgi * recent.position.map({"GK": 5, "DEF": 5, "MID": 4, "FWD": 4})
    nonattack = (residual.groupby(recent.element).sum().reindex(data.index).fillna(0) +
                 0.4) / (data.n.fillna(0) + 2)
    attack_rate = (expected_attacking + 0.45) / (data.minutes.fillna(0) + 135)
    # Match-level club form computed solely from matches available at the cutoff.
    games = fixtures[fixtures.id.isin(history.fixture.unique())].copy()
    scored = pd.concat([games.set_index("team_h").team_h_score,
                        games.set_index("team_a").team_a_score])
    conceded = pd.concat([games.set_index("team_h").team_a_score,
                          games.set_index("team_a").team_h_score])
    strength = (scored.groupby(level=0).mean() - conceded.groupby(level=0).mean())
    data["strength"] = data.club.map(strength).fillna(0)
    data["schedule"] = 1.0
    if final_schedule:
        window = fixtures[fixtures.event.between(gw, gw+horizon-1)]
        opponents = pd.concat([
            pd.Series(1.06-0.10*window.team_a.map(strength).fillna(0).to_numpy(),
                      index=window.team_h),
            pd.Series(0.94-0.10*window.team_h.map(strength).fillna(0).to_numpy(),
                      index=window.team_a),
        ])
        data["schedule"] = data.club.map(opponents.groupby(level=0).sum()).fillna(0) / horizon
    # The per-week forecast is held constant across the intended ownership window.
    data["xp"] = (data.xm.gt(0)*np.minimum(data.xm/30, 2) + nonattack +
                  data.xm*attack_rate) * data.schedule
    data["q"] = data.xp - 0.25 * data.uncertainty
    for pos, group in data.groupby("pos"):
        cheap = group[group.price <= group.price.quantile(0.30)]
        replacement = cheap.q.quantile(0.75)
        scarcity = max(0.10, (group.q.quantile(0.85) - replacement) / 2.0)
        premium = (group.price - FLOOR[pos]) / 10
        surplus = group.q - replacement
        data.loc[group.index, "gap"] = surplus - scarcity * premium
        data.loc[group.index, "gap_ratio"] = surplus / (0.5 + premium.clip(lower=0))
    return data


def market(panel):
    rows = []
    for signal in SIGNALS:
        group = panel.dropna(subset=["change", signal]).copy()
        features = group[["price", "strength", "xm", "minutes", "schedule", signal]]
        controls = pd.get_dummies(group.pos, drop_first=True, dtype=float)
        features = pd.concat([features, controls], axis=1).astype(float)
        # Origin fixed effects absorb season-wide inflation and ownership growth.
        cohorts = group[["season", "gw"]].apply(tuple, axis=1)
        features -= features.groupby(cohorts).transform("mean")
        y = group.change - group.change.groupby(cohorts).transform("mean")
        x = features.to_numpy()
        target = features.columns.get_loc(signal)
        sd = x[:, target].std()
        if not sd:
            continue
        x[:, target] /= sd
        bread = np.linalg.pinv(x.T @ x)
        beta = bread @ x.T @ y
        score = x * (y - x @ beta).to_numpy()[:, None]
        influence = score @ bread[:, target]
        gameweeks = group.assign(influence=influence).groupby(["season", "gw"]).influence.sum()
        variance = float(gameweeks @ gameweeks)
        for _, season in gameweeks.groupby(level=0):
            for lag in range(1, 9):
                variance += 2 * (1 - lag/9) * float(season @ season.shift(lag).fillna(0))
        player = group.assign(influence=influence).groupby(["season", "id"]).influence.sum()
        # Report both marginal dependence sensitivities and use the larger SE.
        se = max(np.sqrt(max(0, variance)), np.sqrt(player @ player))
        df = len(gameweeks) - 1
        rows.append({"signal": signal, "n": len(group), "origins": len(gameweeks),
                     "price_effect_m_per_sd": beta[target],
                     "low": beta[target]-t.ppf(.975, df)*se,
                     "high": beta[target]+t.ppf(.975, df)*se,
                     "p": 2*t.sf(abs(beta[target]/se), df) if se else 1.0})
    adjusted = 0
    for rank, row in enumerate(sorted(rows, key=lambda row: row["p"])):
        adjusted = max(adjusted, min(1, (len(rows)-rank)*row["p"]))
        row["holm"] = adjusted
    return rows


def lineup(squad, info, xp):
    by_position = [sorted((i for i in squad if info[i][0] == pos),
                          key=lambda i: (-xp[i], i)) for pos in SLOTS]
    teams = [tuple(i for pool, count in zip(by_position, formation)
                   for i in pool[:count]) for formation in FORMATIONS]
    starters = max(teams, key=lambda team: sum(xp[i] for i in team) +
                   max(xp[i] for i in team))
    captain, vice = sorted(starters, key=lambda i: (-xp[i], i))[:2]
    bench = sorted(set(squad)-set(starters), key=lambda i: (-xp[i], i))
    return starters, captain, vice, bench


def score(line, actual, info):
    starters, captain, vice, bench = line
    played = {i for i in starters if actual.get(i, (0, 0))[1] > 0}
    absent = [i for i in starters if i not in played]
    # Bench priority, subject to a valid formation after filling vacancies.
    for sub in bench:
        if actual.get(sub, (0, 0))[1] == 0:
            continue
        compatible = [i for i in absent if (info[i][0] == "GK") == (info[sub][0] == "GK")]
        for out in compatible:
            tentative = (played | {sub}) | (set(absent)-{out})
            if all(sum(info[i][0] == pos for i in tentative) >= n for pos, n in MINIMUM.items()):
                played.add(sub)
                absent.remove(out)
                break
    return (sum(actual[i][0] for i in played) +
            (actual[captain][0] if captain in played else
             actual[vice][0] if vice in played else 0))


def sell_price(paid, current):
    return min(current, paid + (current-paid)//2)


def transfer_cost(count, free, cap):
    return 4*max(0, count-free), min(cap, max(0, free-count)+1)


def replay(season, weekly, snapshots, horizon, seed, arm):
    rng = np.random.default_rng(seed)
    first = snapshots[8]
    info = first[["pos", "club", "price"]].apply(tuple, axis=1).to_dict()
    # Start squads are paired across arms. Initial allocation has no price hindsight.
    bank = 1000
    squad = {}
    for pos, count in SLOTS.items():
        pool = first[first.pos.eq(pos)].copy()
        pool["rank"] = pool.q + rng.normal(0, .8, len(pool)) - .06*(pool.price-FLOOR[pos])
        for i in pool.sort_values("rank", ascending=False).index:
            if sum(info[j][0] == pos for j in squad) == count:
                break
            club, price = info[i][1:]
            if sum(info[j][1] == club for j in squad) < 3 and price <= FLOOR[pos]+18 and price <= bank:
                squad[i] = price
                bank -= price
    assert len(squad) == 15
    free = 1
    rows = []
    for gw, data in snapshots.items():
        info.update(data[["pos", "club", "price"]].apply(tuple, axis=1).to_dict())
        xp = data.q.to_dict() | {i: 0 for i in squad if i not in data.index}
        gap = data.gap.to_dict()
        # Standardise market signals within position and cap extreme ranks.
        market_data = data[["ownership", "momentum"]]
        res = market_data-market_data.groupby(data.pos).transform("mean")
        z = (res / res.groupby(data.pos).transform("std").replace(0, np.nan)).fillna(0).clip(-3, 3)
        signals = {"baseline": data.q*0, "value": .55*data.gap,
                   "contrarian": -.5*z.ownership, "momentum": .5*z.momentum,
                   "combined": .55*data.gap-.25*z.ownership+.25*z.momentum}
        tilt = signals[arm].to_dict()
        def objective(ids):
            start, captain, _, bench = lineup(ids, info, xp)
            return (sum(xp[i] for i in start)+xp[captain]+.15*sum(xp[i] for i in bench)
                    +sum(tilt.get(i, 0) for i in ids))
        initial = objective(squad)
        cap = 5 if season == "2024-25" else 2
        best = (0.45, ())
        rank = data.q + signals[arm]
        pools = {pos: list(rank[data.pos.eq(pos)].nlargest(12).index) for pos in SLOTS}
        moves = []
        for out in sorted(squad):
            pos, _, price = info[out]
            kept = set(squad)-{out}
            for new in pools[pos]:
                if new in squad:
                    continue
                cash = sell_price(squad[out], price) - info[new][2]
                gain = objective(kept | {new}) - initial
                moves.append((gain, cash, out, new))

        def consider(bundle):
            nonlocal best
            if bank + sum(move[1] for move in bundle) < 0:
                return
            outgoing = {move[2] for move in bundle}
            incoming = {move[3] for move in bundle}
            if len(outgoing) != len(bundle) or len(incoming) != len(bundle):
                return
            proposed = (set(squad)-outgoing) | incoming
            clubs = [info[i][1] for i in proposed]
            if any(clubs.count(club) > 3 for club in set(clubs)):
                return
            hit, _ = transfer_cost(len(bundle), free, cap)
            gain = min(horizon, 39-gw)*(objective(proposed)-initial) - hit
            if gain > best[0]:
                best = (gain, bundle)

        for move in moves:
            consider((move,))
        # Include funding moves as well as high standalone gains.
        beam = list(dict.fromkeys(sorted(moves, reverse=True)[:8] +
                                  sorted(moves, key=lambda move: -move[1])[:4]))
        for pair in itertools.combinations(beam, 2):
            consider(pair)
        _, bundle = best
        hit, free = transfer_cost(len(bundle), free, cap)
        for _, cash, out, new in bundle:
            bank += cash
            del squad[out]
            squad[new] = info[new][2]
        actual = weekly.xs(gw)[["points", "minutes"]].apply(tuple, axis=1).to_dict()
        points = score(lineup(squad, info, xp), actual, info) - hit
        rows.append({"season": season, "gw": gw, "horizon": horizon, "seed": seed,
                     "arm": arm, "points": points, "hit": hit, "transfer": len(bundle),
                     "bank": bank})
    return rows


def summarize(ledger):
    totals = ledger.groupby(["season", "horizon", "seed", "arm"])[
        ["points", "hit", "transfer"]].sum().reset_index()
    weekly = ledger.pivot(index=["season", "horizon", "seed", "gw"],
                          columns="arm", values="points")
    delta = weekly.drop(columns="baseline").sub(weekly.baseline, axis=0)
    # Average starts before resampling contiguous weeks, preserving pairing.
    delta = delta.groupby(["season", "horizon", "gw"]).mean()
    rng = np.random.default_rng(20261128)
    effects = []
    for (season, horizon), pool in delta.groupby(level=[0, 1]):
        n = len(pool)
        blocks = (rng.integers(0, n, (3000, (n+5)//6, 1)) + np.arange(6)) % n
        samples = pool.to_numpy()[blocks.reshape(3000, -1)[:, :n]].sum(axis=1)
        for j, arm in enumerate(pool.columns):
            low, high = np.quantile(samples[:, j], [.025, .975])
            effects.append({"season": season, "horizon": horizon, "arm": arm,
                            "delta": pool[arm].sum(), "low": low, "high": high})
    return totals, pd.DataFrame(effects)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--market-only", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    audit, panels, ledger = {}, [], []
    for season in SEASONS:
        raw, weekly, fixtures, audit[season] = read_season(args.data, season)
        for schedule in (False, True):
            for horizon in (2, 4, 6):
                if horizon != 4 and (schedule or args.market_only):
                    continue
                snapshots = {gw: snapshot(raw, fixtures, gw, horizon, schedule)
                             for gw in range(8, 39)}
                if horizon == 4:
                    for gw in range(8, 36):
                        d = snapshots[gw].copy()
                        d["change"] = (weekly.xs(gw+3).price - weekly.xs(gw).price)/10
                        panels.append(d.assign(gw=gw, season=season, id=d.index,
                                               final_schedule=schedule))
                if not schedule and not args.market_only:
                    for seed in (11, 33, 55):
                        for arm in ("baseline", "value", "contrarian", "momentum", "combined"):
                            ledger.extend(replay(season, weekly, snapshots, horizon, seed, arm))
        print(season, flush=True)
    panel = pd.concat(panels, ignore_index=True)
    findings = []
    for schedule in (False, True):
        for split, seasons in (("development", SEASONS[:1]), ("holdout", SEASONS[1:])):
            sample = panel[panel.season.isin(seasons) & panel.final_schedule.eq(schedule)]
            result = market(sample)
            findings.extend(dict(row, split=split, final_schedule=schedule) for row in result)
    findings = pd.DataFrame(findings)
    findings.to_csv(args.output / "market.csv", index=False, float_format="%.6f")
    by_season = []
    for (season, schedule), group in panel.groupby(["season", "final_schedule"]):
        by_season.extend(dict(row, season=season, final_schedule=schedule)
                         for row in market(group))
    pd.DataFrame(by_season).to_csv(args.output / "market_by_season.csv", index=False,
                                   float_format="%.6f")
    (args.output / "data_audit.json").write_text(json.dumps(audit, indent=2)+"\n")
    if args.market_only:
        return
    ledger = pd.DataFrame(ledger)
    totals, effects = summarize(ledger)
    for filename, frame in (("weekly_replay", ledger), ("replay_totals", totals),
                            ("paired_effects", effects)):
        frame.to_csv(args.output / f"{filename}.csv", index=False, float_format="%.6f")
    subset = effects[effects.season.isin(SEASONS[1:]) & effects.horizon.eq(4)]
    fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
    for offset, (season, rows) in zip((-.12, .12), subset.groupby("season")):
        ax.errorbar(rows.delta, np.arange(len(rows))+offset,
                    xerr=[rows.delta-rows.low, rows.high-rows.delta], fmt="o", label=season)
    ax.axvline(0, color="0.5", lw=1)
    ax.set(yticks=np.arange(4), yticklabels=subset.arm.unique(),
           xlabel="Points vs proxy baseline, GW8–38 (95% block intervals)")
    ax.legend()
    fig.savefig(args.output/"replay.png", dpi=150)
    plt.close(fig)
    subset = findings[findings.split.eq("holdout") & findings.final_schedule]
    fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
    center = subset.price_effect_m_per_sd
    ax.errorbar(center, subset.signal, xerr=[center-subset.low, subset.high-center], fmt="o")
    ax.axvline(0, color="0.5", lw=1)
    ax.set(xlabel="Change in £m over three GWs per SD (95% marginal intervals)")
    fig.savefig(args.output/"market.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
