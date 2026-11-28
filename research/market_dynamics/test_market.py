"""Contract tests use small artificial fixtures, never historical substitutions."""
import numpy as np
import pandas as pd
import pytest

from data import WEEKLY_BASE, add_market, aligned, outcome_form, price_target
from models import block_samples, price_forecasts, price_metrics, slices
from replay import initial_squad, nominations, realized_score, selling_price, transfer


def market_rows(days=(1, 2, 3, 4, 5)):
    return pd.DataFrame([
        {"season": season, "period": day, "player": p, "code": p,
         "time": pd.Timestamp(2025 + season_index, 10, day, 2, tz="UTC"),
         "tin": 100 * day * p, "tout": 15 * day * p, "ownership": p * .2 + day,
         "price": 52 + day * ((p % 3) - 1), "total_minutes": 50 * day,
         "total_points": 2 * day, "managers": 1_000_000}
        for season_index, season in enumerate(("2025-26", "2026-27")) for day in days
        for p in range(1, 40)
    ])


def test_market_lags_require_exact_dates_and_stable_identity():
    rows = market_rows(days=(1, 2, 4, 5))
    rows.loc[(rows.season == "2025-26") & (rows.period == 5) & (rows.player == 2), "code"] = 999
    data = add_market(rows, daily=True)
    assert data.loc[data.period.eq(4), "flow"].isna().all()
    assert data.loc[data.period.eq(5), "last_flow"].isna().all()
    player = data.query("season == '2025-26' and period == 5 and player == 2").iloc[0]
    assert np.isnan(player.flow)
    assert np.isnan(player.last_price_change)
    assert data.loc[data.period.eq(1), "flow"].isna().all()


def test_counter_corrections_are_missing_and_acceleration_is_backward_only():
    rows = market_rows()
    rows.loc[(rows.season == "2025-26") & (rows.period == 4) & (rows.player == 2), "tin"] = 0
    data = add_market(rows, daily=True)
    correction = data.query("season == '2025-26' and period == 4 and player == 2").iloc[0]
    assert correction.known_counter_correction
    assert np.isnan(correction.flow)
    same = data.query("season == '2025-26' and period == 3 and player == 1").iloc[0]
    assert same.flow == pytest.approx(np.arcsinh(.085))
    assert same.acceleration == 0


def test_horizon_does_not_jump_missing_player_or_cross_season():
    rows = market_rows()
    rows = rows[~((rows.season == "2025-26") & (rows.period == 4) & (rows.player == 2))]
    panel = add_market(rows, daily=True)
    target = price_target(panel, 1, daily=True)
    assert not len(target.query("season == '2025-26' and period == 3 and player == 2"))
    assert not target.period.eq(5).any()
    assert set(target.label) == {0, 1, 2}
    three = aligned(panel, ["code"], 3, "_target")
    assert three.loc[three.period.eq(3), "code_target"].isna().all()


def test_walk_forward_excludes_unmatured_labels():
    first = pd.Timestamp("2025-01-01T00:00Z")
    frame = pd.DataFrame({"season": "one", "time": pd.date_range(first, periods=12)})
    frame["end"] = frame.time + pd.Timedelta(days=3)
    for train, test in slices(frame, cadence=2, warmup=2, end="end"):
        assert train.end.max() <= test.time.min()
        assert train.time.max() < test.time.min()
        assert not train.index.intersection(test.index).size


def test_score_inclusion_and_origin_forecast_are_separate(monkeypatch):
    monkeypatch.setitem(__import__("models").WARMUP, "weekly", 2)
    rows = market_rows(days=range(1, 12))
    missing = (rows.season == "2025-26") & (rows.period == 10) & (rows.player == 5)
    panel = add_market(rows[~missing], daily=False)
    for feature in set(WEEKLY_BASE) - set(panel.columns):
        panel[feature] = 1.0
    predictions = price_forecasts(panel, 1, "weekly")
    unlabelled = predictions.query("season == '2025-26' and period == 9 and player == 5")
    assert len(unlabelled) == 7
    assert unlabelled.label.isna().all()
    assert np.allclose(unlabelled[["p_fall", "p_flat", "p_rise"]].sum(axis=1), 1)
    scores, _ = price_metrics(predictions, 4)
    assert scores.query("scope == 'all'").rows.nunique() == 1
    assert (predictions.train_last_observed <= predictions.time).all()


def test_form_cannot_see_current_or_unfinalized_points():
    quotes = pd.DataFrame({"player": [4, 8]})
    outcomes = pd.DataFrame({
        "player": [4, 4, 4, 4], "period": [1, 3, 4, 5], "points": [5, 6, 99, 99],
        "minutes": [70, 80, 90, 80], "xg": [0, 0, 8, 9], "xa": [0, 0, 9, 8],
    })
    result = outcome_form(quotes, outcomes, {1, 3, 5}, 5).set_index("player")
    assert result.loc[4, "form_points"] == 5.5
    assert result.loc[4, "form_minutes"] == 75
    assert result.loc[8, "form_n"] == 0
    assert np.isnan(result.loc[8, "form_points"])


def test_bootstrap_keeps_origin_season_strata():
    index = pd.MultiIndex.from_tuples([("first", n) for n in range(5)] +
                                      [("second", n) for n in range(5)])
    sample = block_samples(index, 3, draws=12)
    assert sample.shape == (12, 10)
    assert (sample[:, :5] < 5).all()
    assert (sample[:, 5:] >= 5).all()


def pool():
    positions = ["GK"] * 3 + ["DEF"] * 7 + ["MID"] * 7 + ["FWD"] * 5
    data = pd.DataFrame({"player": range(1, len(positions) + 1), "position": positions})
    data = data.set_index("player", drop=False).rename_axis(None)
    data["price"] = 50
    data["club"] = data.player % 8
    data["base_points"] = data.player / 5
    data["points"] = 3
    data["minutes"] = 90
    data["selectable"] = True
    return data


def test_stateful_sale_prices_and_transfer_budget():
    assert selling_price(55, 50) == 52
    assert selling_price(45, 50) == 45
    data = pool()
    bought = initial_squad(data)
    assert len(bought) == 15
    target = next(p for p in data.index if p not in bought)
    held = next(p for p in bought if data.loc[p, "position"] == data.loc[target, "position"])
    data.loc[held, ["price", "base_points"]] = [57, 0]
    data.loc[target, ["price", "base_points"]] = [54, 100]
    outgoing, incoming, bank = transfer(data, bought, 0, "base_points")
    assert incoming != target
    outgoing, incoming, bank = transfer(data, bought, 1, "base_points")
    assert (outgoing, incoming, bank) == (held, target, 0)


def test_realized_nomination_auto_sub_and_captain():
    data = pool()
    bought = initial_squad(data)
    owned = data.loc[list(bought)].copy()
    starters, bench, reserve, captains = nominations(owned)
    assert len(starters) == 11 and len(bench) == 3
    assert realized_score(owned, starters, bench, reserve, captains) == 36
    owned.loc[captains[0], ["points", "minutes"]] = [0, 0]
    owned.loc[captains[1], "points"] = 7
    assert realized_score(owned, starters, bench, reserve, captains) == 44
    owned.loc[bench[0], "minutes"] = np.nan
    assert realized_score(owned, starters, bench, reserve, captains) is None
