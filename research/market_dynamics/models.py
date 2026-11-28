"""Expanding-window comparisons and paired time-block inference."""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from data import DAILY_BASE, MARKET, WEEKLY_BASE, price_target

CLASS_NAMES = ("fall", "flat", "rise")
SEED = 911
DRAWS = 999
BINS = [0, .01, .025, .05, .10, .20, .35, .50, .70, .90, 1.01]
WARMUP = {"daily": 42, "weekly": 20}


def scaled(estimator):
    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
                         StandardScaler(), estimator)


def fit_logistic(train, test, features, strength):
    model = scaled(LogisticRegression(C=strength, max_iter=300))
    model.fit(train[features], train.label)
    return model.predict_proba(test[features])


def slices(data, cadence, warmup, end, skip_seasons=(), test_pool=None):
    if test_pool is None:
        test_pool = data
    for season, one in test_pool.groupby("season", sort=True):
        if season in skip_seasons:
            continue
        origins = sorted(one.time.unique())
        for start in range(0, len(origins), cadence):
            first = origins[start]
            train = data[data[end].le(first) & data.time.lt(first)]
            if train.time.nunique() < warmup:
                continue
            test = one[one.time.isin(origins[start:start + cadence])]
            assert train[end].max() <= test.time.min()
            yield train, test


def bin_forecast(train, test):
    edges = [-np.inf, -2, -.5, .5, 2, np.inf]
    counts = pd.crosstab(np.digitize(train.flow, edges), train.label).reindex(
        index=range(1, len(edges)), columns=range(3), fill_value=0).to_numpy()
    counts = counts + 5
    probabilities = counts / counts.sum(axis=1, keepdims=True)
    return probabilities[np.digitize(test.flow, edges) - 1]


def price_forecasts(panel, horizon, frequency):
    daily = frequency == "daily"
    base = DAILY_BASE if daily else WEEKLY_BASE
    data = price_target(panel, horizon, daily)
    keys = ["season", "period", "time", "player"]
    origin_pool = panel.dropna(subset=["flow", "last_flow"]).merge(
        data[keys + ["time_end", "label"]], on=keys, how="left", validate="one_to_one")
    frames = []
    for train, test in slices(data, 7 if daily else 4, WARMUP[frequency], "time_end",
                              () if daily else ("2022-23",), test_pool=origin_pool):
        if train.label.nunique() < 3:
            continue
        counts = np.bincount(train.label, minlength=3) + 1
        features = base + MARKET
        nonlinear = HistGradientBoostingClassifier(max_iter=45, max_leaf_nodes=9, max_depth=3,
                                                    min_samples_leaf=80, l2_regularization=4,
                                                    early_stopping=False, random_state=SEED)
        nonlinear.fit(train[features], train.label)
        arms = {
            "climatology": np.tile(counts / counts.sum(), (len(test), 1)),
            "flow_bins": bin_forecast(train, test),
            "logit_without_flow": fit_logistic(train, test, base, 10),
            "logit_flow": fit_logistic(train, test, ["flow", "price"], 10),
            "logit_flow_momentum": fit_logistic(train, test, ["flow", "acceleration", "price"], 10),
            "logit_l2_full": fit_logistic(train, test, features, .1),
            "boost_full": nonlinear.predict_proba(test[features]),
        }
        for arm, probabilities in arms.items():
            frame = test[keys + ["time_end", "label"]].reset_index(drop=True).copy()
            frame[["p_fall", "p_flat", "p_rise"]] = probabilities
            frame["model"] = arm
            frame["train_last_observed"] = train.time_end.max()
            frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def sports_forecasts(panel):
    features = WEEKLY_BASE
    frames = []
    for train, test in slices(panel, 4, 20, "final_at", ("2022-23",)):
        train = train.dropna(subset=["minutes", "points"])
        packed = ["season", "time", "period", "player", "points", "minutes"]
        frame = test[packed].copy()
        frame["train_last_observed"] = train.final_at.max()
        for arm, inputs in [("base", features), ("market", features + MARKET)]:
            for target in ("minutes", "points"):
                regressor = scaled(Ridge(alpha=100))
                regressor.fit(train[inputs], train[target])
                frame[f"{arm}_{target}"] = regressor.predict(test[inputs])
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def block_samples(index, width, draws=DRAWS, seed=SEED):
    """Moving, circular blocks over ordered observed origins, stratified by season."""
    random = np.random.default_rng(seed)
    selections, cursor = [], 0
    for _, data in pd.Series(np.arange(len(index)), index=index).groupby(level=0, sort=False):
        size = len(data)
        length = min(width, size)
        starts = random.integers(0, size, size=(draws, (size + length - 1) // length))
        positions = (starts[:, :, None] + np.arange(length)) % size
        selections.append(positions.reshape(draws, -1)[:, :size] + cursor)
        cursor += size
    return np.concatenate(selections, axis=1)


def interval(draws):
    values = np.asarray(draws)
    return np.nanquantile(values, [.025, .975]).tolist() if np.isfinite(values).any() else [None, None]


def summary_by_origin(rows, value, width=4):
    counts = rows.groupby(["season", "period"])[value].agg(["sum", "count"]).sort_index()
    counts = counts[counts["count"] > 0]
    if counts.empty:
        return {"mean": None, "ci95": [None, None], "rows": 0, "origins": 0}
    draw = block_samples(counts.index, width)
    values = counts.to_numpy()
    sums = values[draw].sum(axis=1)
    return {"mean": values[:, 0].sum() / values[:, 1].sum(),
            "ci95": interval(sums[:, 0] / sums[:, 1]),
            "rows": int(values[:, 1].sum()), "origins": len(values)}


def numeric_scores(totals):
    with np.errstate(divide="ignore", invalid="ignore"):
        precision = totals[..., 4:7] / totals[..., 7:10]
        defined = np.isfinite(precision).sum(axis=-1)
        macro = np.nansum(precision, axis=-1) / defined
        scores = np.concatenate([totals[..., :3] / totals[..., 3:4],
                                 precision, np.expand_dims(macro, axis=-1)], axis=-1)
    return scores


def price_metrics(forecasts, width):
    forecasts = forecasts.dropna(subset=["label"])
    metrics, calibration = [], []
    value_columns = ["brier", "log_loss", "accuracy", "n"] + [
        f"{kind}_{i}" for kind in ("correct", "predicted") for i in range(3)]
    metric_names = ["brier", "log_loss", "accuracy", *[f"precision_{x}" for x in CLASS_NAMES],
                    "precision_macro_defined_classes"]
    strata = [("all", forecasts), *list(forecasts.groupby("season"))]
    for name, frame in strata:
        if frame.empty:
            continue
        by_model = {}
        for model, arm in frame.groupby("model"):
            probs = arm[["p_fall", "p_flat", "p_rise"]].to_numpy()
            actual = arm.label.to_numpy(dtype=int)
            hit = np.eye(3)[actual]
            predicted = np.argmax(probs, axis=1)
            scores = pd.DataFrame({
                "season": arm.season, "time": arm.time, "n": 1,
                "brier": np.square(probs - hit).sum(axis=1),
                "log_loss": -np.log(probs[np.arange(len(actual)), actual].clip(1e-15, 1)),
                "accuracy": predicted == actual,
            })
            for index, cls in enumerate(CLASS_NAMES):
                scores[f"correct_{index}"] = (predicted == index) & (actual == index)
                scores[f"predicted_{index}"] = predicted == index
                bins = pd.cut(probs[:, index], bins=BINS, right=False, labels=False)
                reliability = pd.DataFrame({"bin": bins, "p": probs[:, index], "y": hit[:, index]})
                for slot, cell in reliability.groupby("bin"):
                    calibration.append({"scope": name, "model": model, "class": cls,
                                        "bin_low": BINS[slot], "bin_high": min(BINS[slot + 1], 1),
                                        "n": len(cell), "predicted": cell.p.mean(),
                                        "observed": cell.y.mean()})
            by_model[model] = scores.groupby(["season", "time"])[value_columns].sum().sort_index()
        base = by_model["climatology"]
        samples = block_samples(base.index, width)
        baseline_samples = numeric_scores(base.to_numpy()[samples].sum(axis=1))
        for model, table in by_model.items():
            assert table.index.equals(base.index)
            values = table.to_numpy()
            point = numeric_scores(values.sum(axis=0))
            uncertainty = numeric_scores(values[samples].sum(axis=1))
            row = {"scope": name, "model": model, "rows": int(values[:, 3].sum()),
                   "origins": len(table)}
            for i, metric in enumerate(metric_names):
                row[metric] = point[i]
                row[metric + "_lo"], row[metric + "_hi"] = interval(uncertainty[:, i])
            for i, metric in enumerate(metric_names[:2]):
                row[metric + "_delta_vs_climatology_lo"], row[metric + "_delta_vs_climatology_hi"] = interval(
                    uncertainty[:, i] - baseline_samples[:, i])
            row.update({f"argmax_{cls}": int(values[:, 7 + i].sum())
                        for i, cls in enumerate(CLASS_NAMES)})
            metrics.append(row)
    return pd.DataFrame(metrics), pd.DataFrame(calibration)


def sports_metrics(forecasts):
    output = []
    for name, frame in [("all", forecasts), *list(forecasts.groupby("season"))]:
        for target in ("points", "minutes"):
            frame = frame.dropna(subset=[target]).copy()
            errors = {arm: frame[f"{arm}_{target}"] - frame[target] for arm in ("base", "market")}
            frame["delta_mae"] = errors["market"].abs() - errors["base"].abs()
            frame["delta_mse"] = errors["market"] ** 2 - errors["base"] ** 2
            output.append({"scope": name, "target": target, "base_mae": errors["base"].abs().mean(),
                           "market_mae": errors["market"].abs().mean(),
                           "base_rmse": np.sqrt((errors["base"] ** 2).mean()),
                           "market_rmse": np.sqrt((errors["market"] ** 2).mean()),
                           "paired_mae": summary_by_origin(frame, "delta_mae"),
                           "paired_mse": summary_by_origin(frame, "delta_mse")})
    return output
