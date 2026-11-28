"""Descriptive lag, concentration and matched-event estimates."""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from data import aligned
from models import summary_by_origin

GROUP = ["season", "period"]


def rank_relationship(rows, x, y, controls=()):
    output = []
    for key, frame in rows.groupby(GROUP):
        sample = frame[[x, y, *controls]].dropna()
        if len(sample) < 40:
            continue
        ranks = sample.rank().to_numpy()
        responses = ranks[:, :2]
        if controls:
            design = np.column_stack([np.ones(len(sample)), ranks[:, 2:]])
            fitted = design @ np.linalg.lstsq(design, responses, rcond=None)[0]
            responses = responses - fitted
        if np.any(responses.std(axis=0) < 1e-8):
            continue
        rho = np.corrcoef(responses.T)[0, 1]
        output.append((*key, rho, len(sample)))
    result = pd.DataFrame(output, columns=[*GROUP, "rho", "eligible_players"])
    summary = summary_by_origin(result, "rho")
    summary["eligible_player_rows"] = int(result.eligible_players.sum())
    return summary


def matched(frame, treatment, endpoints, all_controls=None):
    """Match with replacement within season/GW, position and availability."""
    output = []
    controls = ~treatment if all_controls is None else all_controls
    frame = frame.assign(treatment=treatment, control=controls, log_own=np.log1p(frame.ownership))
    scale = np.array([2, 25, 1, 15])
    match_columns = ["form_points", "form_minutes", "log_own", "price"]
    for key, group in frame.groupby([*GROUP, "position", "fit"]):
        eligible = group.dropna(subset=match_columns + endpoints)
        cases, pool = eligible[eligible.treatment], eligible[eligible.control]
        if cases.empty or pool.empty:
            continue
        distance, index = cKDTree(pool[match_columns].to_numpy() / scale).query(
            cases[match_columns].to_numpy() / scale)
        differences = cases[endpoints].to_numpy() - pool.iloc[index][endpoints].to_numpy()
        pairs = pd.DataFrame(differences, columns=endpoints)
        pairs["season"], pairs["period"] = key[:2]
        pairs["distance"] = distance
        output.append(pairs)
    if not output:
        return {}
    pairs = pd.concat(output, ignore_index=True)
    return {"candidates": int(treatment.sum()), "matched_cases": len(pairs),
            "median_distance": pairs.distance.median(),
            "estimands": {endpoint: summary_by_origin(pairs, endpoint) for endpoint in endpoints}}


def event_metrics(panel):
    frame = aligned(panel, ["flow", "points", "minutes", "price"], 1, "_next")
    frame = aligned(frame, ["flow", "points", "minutes", "price"], 2, "_two")
    frame = aligned(frame, ["price"], -2, "_two_ago")
    frame["point_surprise"] = frame.points - frame.form_points
    frame["price_return_next"] = frame.price_next - frame.price
    frame["price_return_two"] = frame.price_two - frame.price
    frame["two_week_points_change"] = (frame.points_next + frame.points_two) / 2 - frame.form_points
    frame["two_week_minutes_change"] = (frame.minutes_next + frame.minutes_two) / 2 - frame.form_minutes
    frame["demand_reversal"] = frame.flow_two - frame.flow_next
    frame["points_from_event"] = (frame.points_next + frame.points_two) / 2 - frame.points
    haul = frame.points.ge(10) & frame.point_surprise.ge(8)
    sell_cutoff = frame.flow.where(frame.ownership.ge(1)).groupby(
        [frame.season, frame.period]).transform("quantile", q=.05)
    dump = frame.ownership.ge(1) & frame.flow.lt(0) & frame.flow.le(sell_cutoff)
    episodes = (frame.price - frame.price_two_ago).ge(3) & frame.flow.gt(0) & frame.last_flow.gt(0)
    frame["price_reversed"] = frame.price_return_two.lt(0).astype(float).where(frame.price_return_two.notna())
    return {
        "haul": matched(frame, haul, ["flow_next", "price_return_next", "demand_reversal",
                                     "two_week_points_change", "points_from_event"],
                        frame.points.notna() & ~haul),
        "selloff": matched(frame, dump, ["flow_next", "two_week_points_change",
                                         "two_week_minutes_change", "price_return_two"],
                           frame.ownership.ge(1) & ~dump),
        "price_episode": matched(frame, episodes, ["price_return_two", "price_reversed",
                                                  "two_week_points_change"]),
    }


def concentration(weekly):
    rows = []
    for key, frame in weekly.dropna(subset=["buys", "ownership", "flow"]).groupby(GROUP):
        if frame.buys.sum() == 0:
            continue
        high = frame.nlargest(int(np.ceil(.01 * len(frame))), "buys")
        rows.append((*key, high.buys.sum() / frame.buys.sum(),
                     high.ownership.sum() / frame.ownership.sum()))
    observations = pd.DataFrame(rows, columns=[*GROUP, "buy_share", "ownership_share"])
    return {key: summary_by_origin(observations, key) for key in ("buy_share", "ownership_share")}


def dynamics_metrics(weekly, daily):
    correlations = []
    for panel, name in [(weekly, "weekly"), (daily, "daily")]:
        for offset in range(-2, 3):
            lead = aligned(panel, ["flow", "last_price_change"], offset, "_other")
            width = offset * pd.Timedelta(days=1)
            if name == "daily":
                lead = aligned(lead, ["time"], offset, "_other")
                lead = lead[(lead.time_other - lead.time - width).abs() <= pd.Timedelta(hours=6)]
            for x, y in [("flow", "last_price_change_other"), ("flow", "flow_other"),
                         ("acceleration", "last_price_change_other")]:
                if offset == 0 and y == "flow_other":
                    continue
                correlations.append({"frequency": name, "x": x, "y": y, "offset": offset,
                                     **rank_relationship(lead, x, y)})
            if name == "weekly":
                correlations.append({"frequency": name, "x": "points", "y": "flow_other",
                                     "offset": offset, **rank_relationship(lead, "points", "flow_other")})
    panel = aligned(weekly, ["flow"], 1, "_next").dropna(subset=["flow", "flow_next"]).copy()
    for column in ("flow", "flow_next"):
        panel[column + "_positive_tail"] = panel.groupby(GROUP)[column].rank(pct=True).ge(.95)
    panel["flow_next_positive_tail"] = panel.flow_next_positive_tail.astype(float)
    feedback = rank_relationship(panel, "last_price_change", "flow_next",
                                 ("flow", "form_points", "form_minutes", "ownership", "fit"))
    return {
        "correlations": correlations,
        "events": event_metrics(weekly),
        "concentration": concentration(weekly),
        "positive_tail_next": summary_by_origin(panel[panel.flow_positive_tail], "flow_next_positive_tail"),
        "positive_tail_unconditional": summary_by_origin(panel, "flow_next_positive_tail"),
        "price_leads_flow_controlled_rank": feedback,
    }
