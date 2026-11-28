"""Point-in-time panels and auditable label joins."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256

import numpy as np
import pandas as pd

from fetch import SEASONS, read_json

POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
KEYS = ["season", "player"]
ACTUALS = ["points", "minutes", "xg", "xa"]
SHORT_FEATURES = ["price", "fit", "chance", "total_minutes", "total_points", "days_to_deadline"]
DAILY_BASE = SHORT_FEATURES + ["point_change", "minute_change", "last_price_change"]
WEEKLY_BASE = SHORT_FEATURES + ["form_points", "form_minutes", "form_xg", "form_xa",
                               "form_n", "last_price_change"]
MARKET = ["ownership", "flow", "last_flow", "acceleration", "volume", "sell_pressure",
          "ownership_change"]
PRICE_COHORT = ["price", "flow", "last_flow"]


def timestamp(value):
    return pd.Timestamp(value).tz_convert("UTC")


def hash_file(path):
    return sha256(path.read_bytes()).hexdigest()


def snapshot(boot, season, captured, period):
    captured = timestamp(captured)
    future = [timestamp(event["deadline_time"]) for event in boot["events"]
              if timestamp(event["deadline_time"]) > captured]
    deadline = min(future) if future else pd.NaT
    rows = []
    for player in boot["elements"]:
        if player["element_type"] not in POSITIONS:
            continue
        rows.append({
            "season": season, "period": period, "time": captured, "deadline": deadline,
            "player": player["id"], "code": player["code"], "club": player["team"],
            "position": POSITIONS[player["element_type"]], "price": player["now_cost"],
            "fit": int(player["status"] == "a"), "status": player["status"],
            "chance": player.get("chance_of_playing_next_round"),
            "selectable": bool(player.get("can_transact", True)) and not player.get("removed", False),
            "ownership": float(player["selected_by_percent"]),
            "total_minutes": player["minutes"], "total_points": player["total_points"],
            "tin": player["transfers_in"], "tout": player["transfers_out"],
            "tin_event": player.get("transfers_in_event"), "tout_event": player.get("transfers_out_event"),
            "ep": player.get("ep_next"), "has_news": bool(player.get("news")),
            "has_news_stamp": bool(player.get("news_added")), "managers": boot["total_players"],
            "days_to_deadline": (deadline - captured) / pd.Timedelta(days=1),
        })
    frame = pd.DataFrame(rows)
    frame["deadline"] = pd.to_datetime(frame.deadline, utc=True)
    # API null means no numeric chance was published. Keep it missing for model imputation.
    assert not frame.duplicated(KEYS).any()
    return frame


def labels(root, season):
    path = root / season
    source = pd.read_csv(path / "merged_gw.csv")
    source = source[source.position.isin(POSITIONS.values())].copy()
    deduped = source.drop_duplicates()
    assert not deduped.duplicated(["element", "fixture"]).any()
    market = ["value", "selected", "transfers_in", "transfers_out", "transfers_balance"]
    grouped = deduped.groupby(["element", "GW"])
    fixture = pd.read_csv(path / "fixtures.csv")
    assert fixture.id.is_unique and fixture.finished.all()
    linked = deduped.merge(fixture[["id", "event"]], left_on="fixture", right_on="id",
                           how="left", validate="many_to_one")
    assert linked.event.eq(linked.GW).all()
    outcome = grouped.agg(
        points=("total_points", "sum"), minutes=("minutes", "sum"),
        xg=("expected_goals", "sum"), xa=("expected_assists", "sum"),
        matches=("fixture", "size"),
    ).reset_index().rename(columns={"element": "player", "GW": "period"})
    stages = fixture.assign(finish_bound=pd.to_datetime(fixture.kickoff_time, utc=True)
                            + pd.Timedelta(hours=3)).groupby("event").finish_bound.max()
    frozen = grouped[market].first().reset_index().rename(columns={"element": "player", "GW": "period"})
    old_players = pd.read_csv(path / "players_raw.csv", usecols=["id", "code"])
    audit = {
        "fixture_rows": int(len(source)), "identical_duplicate_rows": int(len(source) - len(deduped)),
        "double_or_triple_player_gws": int((outcome.matches > 1).sum()),
        "market_conflicts_within_gw": (grouped[market].nunique() > 1).sum().to_dict(),
        "source_transfer_balance_disagreements": int((deduped.transfers_in - deduped.transfers_out
                                                       != deduped.transfers_balance).sum()),
        "missing_fields": deduped[market + ["xP", "minutes", "total_points", "expected_goals",
                                           "expected_assists"]].isna().sum().to_dict(),
        "excluded_assistant_manager_fixture_rows": int((pd.read_csv(path / "merged_gw.csv",
                                                       usecols=["position"]).position == "AM").sum()),
        "source_sha256": {name: hash_file(path / name) for name in
                          ("merged_gw.csv", "fixtures.csv", "players_raw.csv")},
    }
    return outcome, frozen, old_players, fixture, stages, audit


def aligned(frame, columns, offset, suffix):
    """Join only exact relative origins within player, calendar and season."""
    copy = frame[KEYS + ["period", *columns]].copy()
    copy["period"] -= offset
    return frame.merge(copy.rename(columns={col: col + suffix for col in columns}),
                       on=KEYS + ["period"], how="left", validate="one_to_one")


def add_market(frame, daily):
    observed = aligned(frame, ["tin", "tout", "time", "price", "ownership", "total_points",
                               "total_minutes", "code"], -1, "_previous")
    valid = observed.code.eq(observed.code_previous)
    elapsed = (observed.time - observed.time_previous) / pd.Timedelta(hours=1)
    if daily:
        valid &= elapsed.between(18, 30)
    ins = observed.tin - observed.tin_previous
    outs = observed.tout - observed.tout_previous
    counts_ok = valid & ins.ge(0) & outs.ge(0) & observed.managers.gt(0)
    scale = 100_000 / observed.managers
    observed["net_raw"] = (ins - outs).where(counts_ok)
    observed["buys"] = ins.where(counts_ok)
    observed["sells"] = outs.where(counts_ok)
    observed["flow"] = np.arcsinh((observed.net_raw * scale) / 100)
    observed["volume"] = np.log1p((ins + outs).where(counts_ok) * scale)
    previous_owners = (observed.ownership_previous / 100 * observed.managers).clip(lower=100)
    observed["sell_pressure"] = (outs / previous_owners).where(counts_ok)
    for current, feature in [("price", "last_price_change"), ("ownership", "ownership_change"),
                             ("total_points", "point_change"), ("total_minutes", "minute_change")]:
        observed[feature] = (observed[current] - observed[current + "_previous"]).where(valid)
    observed = aligned(observed, ["flow"], -1, "_previous_interval")
    observed["last_flow"] = observed.pop("flow_previous_interval").where(valid)
    observed["acceleration"] = observed.flow - observed.last_flow
    observed["known_counter_correction"] = valid & ~counts_ok
    return observed.drop(columns=[col for col in observed if col.endswith("_previous")])


def outcome_form(quotes, outcome, final_gws, gw):
    history = outcome[outcome.period.isin([p for p in final_gws if gw - 4 <= p < gw])]
    form = history.groupby("player")[ACTUALS].mean().add_prefix("form_")
    form["form_n"] = history.groupby("player").size()
    merged = quotes.merge(form, on="player", how="left", validate="one_to_one")
    merged["form_n"] = merged.form_n.fillna(0)
    return merged


def weekly(root, receipt, terminal_receipt):
    panels, audit, inventory = [], {}, []
    for season in SEASONS:
        outcome, frozen, old_players, fixture, stages, audit[season] = labels(root, season)
        sources = sorted((row for row in receipt if row["season"] == season),
                         key=lambda row: row["gw"])
        stamped, final_times = {}, {}
        for row in sources:
            boot = read_json(root / row["file"])
            gw = row["gw"]
            captured = timestamp(row["timestamp"])
            gap = timestamp(row["deadline"]) - captured
            assert pd.Timedelta(hours=1) <= gap <= pd.Timedelta(hours=24)
            target = next(event for event in boot["events"] if event["id"] == gw)
            # A rescheduled deadline absent from a vintage is not substituted.
            if timestamp(target["deadline_time"]) != timestamp(row["deadline"]):
                continue
            quotes = snapshot(boot, season, captured, gw)
            if quotes.deadline.iloc[0] != timestamp(row["deadline"]):
                continue
            final = {event["id"] for event in boot["events"]
                     if event["finished"] and event["data_checked"]
                     and stages.get(event["id"], timestamp(event["deadline_time"])) < captured}
            for period in final:
                final_times.setdefault(period, captured)
            stamped[gw] = (quotes, final)
            inventory.append({**row, "sha256": hash_file(root / row["file"]),
                              "players": len(quotes), "known_final_gws": sorted(final)})
        terminal = next(row for row in terminal_receipt if row["season"] == season)
        terminal_boot = read_json(root / terminal["file"])
        terminal_time = timestamp(terminal["timestamp"])
        for event in terminal_boot["events"]:
            period = event["id"]
            if (event["finished"] and event["data_checked"]
                    and stages.get(period, timestamp(event["deadline_time"])) < terminal_time):
                final_times.setdefault(period, terminal_time)
        frame = pd.concat([part for part, _ in stamped.values()], ignore_index=True)
        lookup = frame[["player", "code"]].drop_duplicates().merge(
            old_players, left_on="player", right_on="id", suffixes=("", "_terminal"))
        ambiguous = set(lookup.loc[lookup.code != lookup.code_terminal, "player"])
        audit[season]["id_vs_terminal_code_mismatch_players"] = len(ambiguous)
        outcome = outcome[~outcome.player.isin(ambiguous)]
        fixture_clubs = {(int(row.event), club) for row in fixture.itertuples()
                         for club in (row.team_h, row.team_a)}
        blank = frame[["player", "club", "period"]].copy()
        blank = blank[[key not in fixture_clubs for key in zip(blank.period, blank.club)]]
        blank = blank.merge(outcome[["player", "period"]], on=["player", "period"],
                            how="left", indicator=True)
        blank = blank[blank._merge == "left_only"][["player", "period"]]
        blank = blank[~blank.player.isin(ambiguous)].assign(**dict.fromkeys(ACTUALS, 0))
        outcome = pd.concat([outcome, blank], ignore_index=True)
        outcome["final_at"] = pd.to_datetime(outcome.period.map(final_times), utc=True)
        panel = pd.concat([outcome_form(part, outcome, final, gw)
                           for gw, (part, final) in stamped.items()], ignore_index=True)
        panel = panel.merge(outcome, on=["player", "period"], how="left", validate="one_to_one")
        market_check = panel.merge(frozen, on=["player", "period"], how="inner", validate="one_to_one")
        audit[season].update(
            weeks=len(stamped), missing_snapshot_gws=sorted(set(range(1, 39)) - set(stamped)),
            player_snapshots=len(panel), unmatched_minutes=int(panel.minutes.isna().sum()),
            source_blank_zeros=len(blank), actual_points_rows=int(panel.points.notna().sum()),
            last_gw_with_observed_finality=max(final_times, default=0),
            raw_ep_next_present=int(panel.ep.notna().sum()),
            status_counts=panel.status.value_counts().to_dict(),
            injury_chance_present=int(panel.chance.notna().sum()),
            news_present=int(panel.has_news.sum()),
            news_timestamp_present=int(panel.has_news_stamp.sum()),
            joined_weekly_history_rows=len(market_check),
            historical_prices_differ=int((market_check.price != market_check.value).sum()),
            historical_event_transfer_in_differ=int((market_check.tin_event != market_check.transfers_in).sum()),
            season_deadline_gap_hours=[float(((panel.deadline - panel.time) / pd.Timedelta(hours=1)).min()),
                                       float(((panel.deadline - panel.time) / pd.Timedelta(hours=1)).max())],
            terminal_evidence={**terminal, "sha256": hash_file(root / terminal["file"])},
        )
        panels.append(panel)
    return add_market(pd.concat(panels, ignore_index=True), daily=False), audit, inventory


def daily(root, cache_receipt):
    parts, inventory = [], []
    for row in cache_receipt:
        time = timestamp(row["timestamp"])
        boot = read_json(root / row["file"])
        parts.append(snapshot(boot, "2025-26", time, time.date().toordinal()))
        inventory.append({**row, "season": "2025-26", "sha256": hash_file(root / row["file"])})
    external = root / "daily" / "raw"
    used_days = set()
    fixture_counts = Counter()
    for path in sorted(external.iterdir()):
        if not path.is_dir():
            continue
        stamp = datetime.strptime(path.name, "%Y-%m-%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        if stamp.date() in used_days:
            continue
        used_days.add(stamp.date())
        boot = path / "bootstrap-static.json.gz"
        parts.append(snapshot(read_json(boot), "2026-27", stamp, stamp.date().toordinal()))
        fixtures = path / "fixtures.json.gz"
        fixture_counts["snapshots"] += fixtures.is_file()
        fixture_counts["rows"] += len(read_json(fixtures)) if fixtures.is_file() else 0
        inventory.append({"timestamp": stamp.isoformat(), "season": "2026-27",
                          "file": str(boot.relative_to(root)), "sha256": hash_file(boot),
                          "fixture_sha256": hash_file(fixtures) if fixtures.is_file() else None})
    market = add_market(pd.concat(parts, ignore_index=True), daily=True)
    audits = {}
    for season, frame in market.groupby("season"):
        stamps = frame[["time", "period"]].drop_duplicates().sort_values("time")
        audits[season] = {
            "observations": len(stamps), "first": stamps.time.min().isoformat(),
            "last": stamps.time.max().isoformat(), "player_snapshots": len(frame),
            "days_missing": int(stamps.period.max() - stamps.period.min() + 1 - len(stamps)),
            "max_interval_hours": float(stamps.time.diff().max() / pd.Timedelta(hours=1)),
            "negative_counter_or_invalid_manager_rows": int(frame.known_counter_correction.sum()),
            "usable_flow_rows": int(frame.flow.notna().sum()),
            "usable_acceleration_rows": int(frame.acceleration.notna().sum()),
            "last_available_deadline": frame.deadline.max().isoformat(),
        }
    audits["fixtures_2026-27"] = dict(fixture_counts)
    return market, audits, inventory


def price_target(frame, horizon, daily):
    joined = aligned(frame, ["price", "time", "code"], horizon, "_end")
    valid = joined.code.eq(joined.code_end)
    if daily:
        hours = (joined.time_end - joined.time) / pd.Timedelta(hours=1)
        low, high = {1: (18, 30), 3: (60, 84)}[horizon]
        valid &= hours.between(low, high)
    subset = joined[valid & joined.flow.notna() & joined.last_flow.notna()].copy()
    subset["label"] = np.sign(subset.price_end - subset.price).astype(int) + 1
    return subset
