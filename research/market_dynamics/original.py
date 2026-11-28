"""Inventory and exploratory check against original published MM and PM."""
import gzip
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from data import hash_file, timestamp
from fetch import DIAGNOSTIC, GW11_COMMIT, read_json


def release_inventory(root):
    releases = []
    tags = (Path(__file__).parent / "release-tags.txt").read_text().splitlines()
    for tag in sorted(tags):
        folder = root / "releases" / tag
        manifest = read_json(folder / "manifest.json")
        publication = read_json(folder / "publication.json")
        provenance = read_json(folder / "official-provenance.json.gz")
        boot = read_json(folder / "official-bootstrap.json.gz")
        verified = {}
        for name in ("forecast.json.gz", "mm.json.gz", "official-provenance.json.gz",
                     "official-bootstrap.json.gz", "official-fixtures.json.gz"):
            verified[name] = hash_file(folder / name)
            assert verified[name] == manifest["files"][name]
        gw = manifest["origin_gw"]
        event = next(e for e in boot["events"] if e["id"] == gw)
        assert (timestamp(provenance["bootstrap_observed_at"]) <= timestamp(manifest["data_cutoff"])
                <= timestamp(publication["publication_at"]) < timestamp(manifest["official_deadline"]))
        releases.append({
            "tag": folder.name, "gw": gw, "forecast_data_cutoff": manifest["data_cutoff"],
            "bootstrap_observed_at": provenance["bootstrap_observed_at"],
            "deadline": manifest["official_deadline"], "publication": publication["publication_at"],
            "model_versions": manifest["model_versions"], "fixture_rows": manifest["player_fixture_rows"],
            "market_and_availability_fields": sorted(set(boot["elements"][0]) & {
                "now_cost", "transfers_in", "transfers_out", "transfers_in_event", "transfers_out_event",
                "selected_by_percent", "status", "news", "news_added", "ep_next", "price_change_percent",
            }),
            "origin_finished_at_forecast": event["finished"],
            "origin_data_checked_at_forecast": event["data_checked"],
            "assets_sha256": verified,
        })
    return releases


def diagnostic_inventory(root):
    path = root / "diagnostic" / "diagnostic-snapshot.zip"
    with ZipFile(path) as archive:
        root_name = "work/live-final-model/predeadline_2026_archives/snapshots/"
        by_gw = {}
        for name in sorted(archive.namelist()):
            if not name.startswith(root_name) or not name.endswith(".json"):
                continue
            document = json.loads(archive.read(name))
            evidence = document["evidence"]
            gw = evidence["gw"]
            stamp = timestamp(evidence["snapshot_at_utc"])
            assert stamp < timestamp(evidence["official_deadline"])
            if gw not in by_gw:
                by_gw[gw] = {"times": set(), "fields": set()}
            period = by_gw[gw]
            period["times"].add(stamp)
            period["fields"].update(document["players"][0])
        raw_capture = sorted(name for name in archive.namelist()
                             if name.startswith("data_v1_1/raw/live-captures/") and name.endswith("/bootstrap.json"))
    return {
        "release": DIAGNOSTIC, "sha256": hash_file(path), "raw_bootstrap_paths": raw_capture,
        "predeadline_archive": [{
            "gw": gw, "distinct_times": len(row["times"]), "fields": sorted(row["fields"]),
            "first": min(row["times"]).isoformat(), "last": max(row["times"]).isoformat(),
        } for gw, row in sorted(by_gw.items())],
    }


def current_finality(root):
    candidates = sorted((root / "daily" / "raw").glob("*/bootstrap-static.json.gz"))
    document = read_json(candidates[-1])
    return {event["id"]: {"finished": event["finished"], "data_checked": event["data_checked"]}
            for event in document["events"] if event["id"] <= 13}


def first_final_live(root, gw):
    for path in sorted((root / "daily" / "raw").glob(f"*/event-{gw}-live.json.gz")):
        document = read_json(path.parent / "bootstrap-static.json.gz")
        event = next(row for row in document["events"] if row["id"] == gw)
        if event["finished"] and event["data_checked"]:
            return path
    raise ValueError(f"No final live payload for GW{gw}")


def input_hash(path):
    data = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    return sha256(data).hexdigest()


def frozen_scores(root, market, archived):
    """One contemporaneous market observation per archived original."""
    report, coverage = [], []
    audit = {row["gw"]: row for row in read_json(archived / "report.json.gz")["weeks"]}
    for gw in (8, 9, 10, 11):
        if gw <= 10:
            assert audit[gw]["status"] == "complete"
            forecast_path = archived / f"gw{gw}-forecast.json.gz"
            mm_path = archived / f"gw{gw}-mm.json.gz"
            live_path = archived / f"gw{gw}-live.json.gz"
            index_path = archived / f"gw{gw}-index.json.gz"
        else:
            assert audit[gw]["publication_commit"] == GW11_COMMIT
            forecast_path = root / "original-gw11" / "forecast.json"
            mm_path = root / "original-gw11" / "mm.json"
            live_path = first_final_live(root, gw)
            index_path = root / "original-gw11" / "index.json"
        index = read_json(index_path)
        forecast, mm, live = map(read_json, [forecast_path, mm_path, live_path])
        cutoff = timestamp(index["data_asof"])
        assert cutoff == timestamp(forecast["data_asof"])
        assert cutoff == timestamp(mm["data_at"])
        assert cutoff <= timestamp(audit[gw]["published_at"]) < timestamp(index["origin_deadline"])
        assert input_hash(forecast_path) == index["forecast_file_sha256"]
        assert input_hash(mm_path) == index["mm_file_sha256"]
        assert index["forecast_sha256"] == audit[gw]["forecast_sha256"]
        prices = {}
        points = {}
        for player in forecast["players"]:
            matching = [week for week in player["weeks"] if week["gw"] == gw]
            assert len(matching) == 1
            prices[player["id"]] = player["price_tenths"]
            points[player["id"]] = float(matching[0]["xpts"])
        selected = market[(market.season == "2026-27") & market.time.le(cutoff)]
        asof = selected.time.max()
        assert cutoff - asof <= pd.Timedelta(hours=36)
        observed = selected[selected.time.eq(asof)]
        minutes = [row for row in mm["players"] if row["gw"] == gw and row["fpl_element"] is not None]
        minutes = pd.DataFrame(minutes).groupby("fpl_element").xmins.agg(["sum", "size"])
        actual = {entry["id"]: entry["stats"] for entry in live["elements"]}
        matched = observed[observed.flow.notna() & observed.player.isin(prices)
                           & observed.player.isin(minutes.index) & observed.player.isin(actual)].copy()
        matched["original_points"] = matched.player.map(points)
        matched["original_minutes"] = matched.player.map(minutes["sum"])
        matched["actual_points"] = matched.player.map({key: value["total_points"] for key, value in actual.items()})
        matched["actual_minutes"] = matched.player.map({key: value["minutes"] for key, value in actual.items()})
        matched["market_points"] = matched.original_points + .25 * matched.flow
        matched["market_minutes"] = (matched.original_minutes + 2.5 * matched.flow).clip(
            lower=0, upper=matched.player.map(minutes["size"]) * 90)
        for target in ("points", "minutes"):
            baseline = matched[f"original_{target}"] - matched[f"actual_{target}"]
            augmented = matched[f"market_{target}"] - matched[f"actual_{target}"]
            report.append({
                "gw": gw, "target": target, "rows": len(matched),
                "residual_flow_spearman": (-baseline).corr(matched.flow, method="spearman"),
                "original_mae": baseline.abs().mean(), "augmented_mae": augmented.abs().mean(),
                "delta_mae": (augmented.abs() - baseline.abs()).mean(),
                "original_rmse": np.sqrt((baseline ** 2).mean()),
                "augmented_rmse": np.sqrt((augmented ** 2).mean()),
            })
        coverage.append({
            "gw": gw, "market_observed_at": asof.isoformat(), "full_mm_pm_matched": len(matched),
            "minutes_players": len(minutes), "points_players": len(points),
            "players_with_price_differences": int((matched.price != matched.player.map(prices)).sum()),
            "forecast_data_cutoff": cutoff.isoformat(),
            "publication_commit": audit[gw]["publication_commit"], "published_at": audit[gw]["published_at"],
            "mm_self_reported_deadline_correct": mm["deadline_correct"],
            "gw11_final_label_vintage": live_path.parent.name if gw == 11 else None,
            "source_sha256": {path.name: hash_file(path) for path in
                              (forecast_path, mm_path, live_path, index_path)},
        })
    return coverage, pd.DataFrame(report)
