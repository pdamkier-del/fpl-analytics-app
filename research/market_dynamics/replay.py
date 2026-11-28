"""Restricted, stateful single-transfer replay. Uses no production model."""
from collections import Counter
from itertools import combinations, product

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp

SQUAD = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
MINIMUM = {"GK": 1, "DEF": 3, "MID": 2, "FWD": 1}
XI_FORMATIONS = [dict(zip(SQUAD, counts)) for counts in product([1], range(3, 6), range(2, 6), range(1, 4))
                 if sum(counts) == 11]


def selling_price(cost, purchase):
    return cost if cost <= purchase else purchase + (cost - purchase) // 2


def initial_squad(pool):
    available = pool[pool.selectable].sort_index()
    features = [available.price.to_numpy()]
    lower, upper = [0], [1000]
    for position, count in SQUAD.items():
        features.append(available.position.eq(position).to_numpy())
        lower.append(count)
        upper.append(count)
    for club in sorted(available.club.unique()):
        features.append(available.club.eq(club).to_numpy())
        lower.append(0)
        upper.append(3)
    objective = -available.base_points.to_numpy() + np.arange(len(available)) * 1e-8
    result = milp(objective, integrality=np.ones(len(available)), bounds=Bounds(0, 1),
                  constraints=LinearConstraint(np.vstack(features), lower, upper))
    assert result.success, result.message
    squad = available[result.x > .5].price.astype(int).to_dict()
    assert len(squad) == 15 and sum(squad.values()) <= 1000
    return squad


def transfer(pool, bought, bank, arm):
    owned = pool.loc[list(bought)]
    candidates = pool[pool.selectable & ~pool.index.isin(bought)]
    candidates = candidates.sort_values([arm, "price", "player"], ascending=[False, True, True])
    club_count = Counter(owned.club)
    best = (.15, None, None, None)
    for outgoing, current in owned.iterrows():
        sale = selling_price(current.price, bought[outgoing])
        permitted = {club for club, count in club_count.items() if count - (club == current.club) >= 3}
        eligible = candidates[(candidates.position == current.position)
                              & (candidates.price <= bank + sale)
                              & ~candidates.club.isin(permitted)]
        if not eligible.empty:
            incoming = eligible.iloc[0]
            remaining = bank + sale - int(incoming.price)
            new_clubs = club_count.copy()
            new_clubs[current.club] -= 1
            new_clubs[incoming.club] += 1
            gain = incoming[arm] - current[arm]
            if max(new_clubs.values()) <= 3 and gain > best[0]:
                best = (gain, outgoing, int(incoming.player), remaining)
    return best[1:]


def nominations(owned):
    ranked = owned.sort_values(["base_points", "player"], ascending=[False, True])
    by_position = {position: ranked[ranked.position == position].player.tolist() for position in SQUAD}
    scores = owned.base_points.to_dict()
    formations = [[player for pos, count in formation.items() for player in by_position[pos][:count]]
                  for formation in XI_FORMATIONS]
    starters = max(formations, key=lambda ids: sum(scores[player] for player in ids))
    outfield_bench = ranked[~ranked.player.isin(starters) & ranked.position.ne("GK")].player.tolist()
    reserve_keeper = next(player for player in by_position["GK"] if player not in starters)
    captains = ranked[ranked.player.isin(starters)].player.iloc[:2].tolist()
    return starters, outfield_bench, reserve_keeper, captains


def realized_score(owned, starters, bench, reserve_keeper, captains):
    minutes = owned.minutes.to_dict()
    points = owned.points.to_dict()
    position = owned.position.to_dict()
    if owned[["minutes", "points"]].isna().any().any():
        return None
    active = [player for player in starters if minutes[player] > 0]
    if not any(position[player] == "GK" for player in active) and minutes[reserve_keeper] > 0:
        active.append(reserve_keeper)
    missing = [player for player in starters if minutes[player] == 0 and position[player] != "GK"]
    eligible = [player for player in bench if minutes[player] > 0]
    original = Counter(position[player] for player in starters)
    for count in range(min(len(missing), len(eligible)), 0, -1):
        selected = None
        for incoming in combinations(eligible, count):
            for outgoing in combinations(missing, count):
                shape = original.copy()
                shape.update(position[player] for player in incoming)
                shape.subtract(position[player] for player in outgoing)
                if all(shape[pos] >= minimum for pos, minimum in MINIMUM.items()):
                    selected = incoming
                    break
            if selected is not None:
                break
        if selected is not None:
            active.extend(selected)
            break
    captain = next((player for player in captains if player in active), None)
    return sum(points[player] for player in active) + points.get(captain, 0)


def season_replay(panel, sports, price_predictions):
    point_fields = ["base_points", "market_points"]
    keys = ["season", "period", "player"]
    # Players without the required past flow observations have a neutral price term.
    quotes = panel[keys + ["club", "position", "price", "selectable", "points", "minutes"]]
    quotes = quotes.merge(sports[keys + point_fields], on=keys, how="inner", validate="one_to_one")
    price = price_predictions[price_predictions.model == "logit_l2_full"]
    # Price predictions for replay come from the live origin pool, independent of future label availability.
    quotes = quotes.merge(price[keys + ["p_rise", "p_fall"]], on=keys, how="left", validate="one_to_one")
    quotes["price_aware"] = quotes.base_points + .25 * (quotes.p_rise - quotes.p_fall).fillna(0)
    ledger = []
    for season, frame in quotes.groupby("season"):
        weeks = dict(tuple(frame.groupby("period", sort=True)))
        assert list(weeks) == list(range(1, 39))
        first = weeks[1].set_index("player", drop=False).rename_axis(None)
        initial = initial_squad(first)
        for arm in ("base_points", "market_points", "price_aware"):
            bought = initial.copy()
            bank = 1000 - sum(bought.values())
            for gw, rows in weeks.items():
                pool = rows.set_index("player", drop=False).rename_axis(None)
                absent = set(bought) - set(pool.index)
                if absent:
                    ledger.append({"season": season, "gw": gw, "arm": arm, "missing_roster": len(absent)})
                    continue
                outgoing, incoming = None, None
                if gw > 1:
                    outgoing, incoming, balance = transfer(pool, bought, bank, arm)
                    if incoming is not None:
                        bank = balance
                        del bought[outgoing]
                        bought[incoming] = int(pool.loc[incoming, "price"])
                owned = pool.loc[list(bought)]
                assert bank >= 0 and Counter(owned.position) == SQUAD
                score = realized_score(owned, *nominations(owned))
                ledger.append({"season": season, "gw": gw, "arm": arm, "points": score,
                               "bank": bank, "squad_sale_value": sum(selling_price(owned.loc[p, "price"], cost)
                                                                    for p, cost in bought.items()),
                               "outgoing": outgoing, "incoming": incoming,
                               "club_excess_before_required_transfer": max(Counter(owned.club).values()) > 3,
                               "missing_roster": 0})
    runs = pd.DataFrame(ledger)
    coverage = runs.groupby(["season", "arm"]).agg(weeks_scored=("points", "count"),
                                                    substitutions_in=("incoming", "count"),
                                                    total_points=("points", "sum")).reset_index()
    reference = runs[runs.arm == "base_points"].set_index(["season", "gw"]).points.rename("control")
    pairs = runs.join(reference, on=["season", "gw"])
    pairs["delta"] = pairs.points - pairs.control
    matched = pairs.groupby(["season", "arm"]).delta.agg(["count", "sum"]).reset_index()
    return runs, coverage.merge(matched.rename(columns={"count": "paired_weeks", "sum": "paired_delta"}),
                                on=["season", "arm"])
