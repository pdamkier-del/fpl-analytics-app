"""Fetch the public source vintages used by this study."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import gzip
import json
import lzma
from pathlib import Path
import subprocess
from time import sleep
from urllib.request import urlopen

WEEKLY_REPO = "vaastav/Fantasy-Premier-League"
WEEKLY_SHA = "7ca01d3821a68ced454cd1f2195be40ed697629b"
CACHE_REPO = "Randdalf/fplcache"
CACHE_SHA = "0c41a046b5fba30e3719f70e3e638ac14c29a3cf"
DAILY_REPO = "eicyer/fpl-snapshots"
DAILY_SHA = "d5d33221409f89386ab3dcbf17b40e65aed639a8"
APP_REPO = "pdamkier-del/fpl-analytics-app"
SEASONS = ("2022-23", "2023-24", "2024-25", "2025-26")
DIAGNOSTIC = "diagnostic-46134764616-1"


def raw(repo, revision, path):
    return f"https://raw.githubusercontent.com/{repo}/{revision}/{path}"


def get(url, path):
    if path.exists():
        return
    for attempt in range(3):
        try:
            with urlopen(url, timeout=30) as response:
                data = response.read()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return
        except OSError:
            if attempt == 2:
                raise
            sleep(2 ** attempt)


def read_json(path):
    opener = {".xz": lzma.open, ".gz": gzip.open}.get(path.suffix, open)
    with opener(path, "rt", encoding="utf-8") as source:
        return json.load(source)


def api(path, dest):
    get(f"https://api.github.com/repos/{CACHE_REPO}/{path}", dest)
    return read_json(dest)["tree"]


def list_cache(root):
    index = root / "index"
    top = api(f"git/trees/{CACHE_SHA}", index / "root.json")
    cache = next(row["sha"] for row in top if row["path"] == "cache")
    years = api(f"git/trees/{cache}", index / "cache.json")
    for year in years:
        if year["path"] not in {"2022", "2023", "2024", "2025", "2026"}:
            continue
        paths = api(f'git/trees/{year["sha"]}?recursive=1', index / f'{year["path"]}.json')
        for item in paths:
            if not item["path"].endswith(".json.xz"):
                continue
            month, day, filename = item["path"].split("/")
            clock = filename.split(".")[0]
            stamp = datetime(int(year["path"]), int(month), int(day),
                             int(clock[:2]), int(clock[2:]), tzinfo=timezone.utc)
            yield stamp, f'cache/{year["path"]}/{item["path"]}'


def fetch_cache(root):
    paths = dict(list_cache(root))

    def download(stamp):
        path = paths[stamp]
        local = root / path
        get(raw(CACHE_REPO, CACHE_SHA, path), local)
        return str(local.relative_to(root))

    selections = {}
    for season in SEASONS:
        year = 2000 + int(season[-2:])
        # Terminal snapshot only locates the search window and confirms the calendar.
        terminal = min(ts for ts in paths if ts >= datetime(year, 5, 31, tzinfo=timezone.utc))
        boot = read_json(root / download(terminal))
        assert len(boot["events"]) == 38 and boot["events"][-1]["data_checked"]
        for event in boot["events"]:
            deadline = datetime.fromisoformat(event["deadline_time"])
            choices = sorted((ts for ts in paths
                              if deadline - timedelta(hours=24) <= ts <= deadline - timedelta(hours=1)),
                             reverse=True)
            if choices:
                selections[season, event["id"]] = (deadline.isoformat(), choices[0])

    # First morning capture at/after 01:00 UTC and before 07:00 UTC, per calendar day.
    morning = {}
    for ts in sorted(paths):
        if datetime(2025, 8, 16, tzinfo=timezone.utc) <= ts < datetime(2026, 5, 26, tzinfo=timezone.utc):
            if 1 <= ts.hour < 7:
                morning.setdefault(ts.date(), ts)
    needed = sorted(set(morning.values()) | {stamp for _, stamp in selections.values()})
    with ThreadPoolExecutor(max_workers=10) as pool:
        downloads = dict(zip(needed, pool.map(download, needed), strict=True))
    receipt = {
        "weekly": [
            {"season": key[0], "gw": key[1], "deadline": deadline, "timestamp": stamp.isoformat(),
             "file": downloads[stamp]}
            for key, (deadline, stamp) in selections.items()
        ],
        "daily": [{"timestamp": stamp.isoformat(), "file": downloads[stamp]} for stamp in morning.values()],
    }
    (root / "cache-selection.json").write_text(json.dumps(receipt, indent=2) + "\n")


def fetch(root):
    root.mkdir(parents=True, exist_ok=True)
    jobs = [(raw(WEEKLY_REPO, WEEKLY_SHA, f"data/{season}/{path}"), root / season / Path(path).name)
            for season in SEASONS for path in ("gws/merged_gw.csv", "fixtures.csv", "players_raw.csv")]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda job: get(*job), jobs))
    daily = root / "daily"
    if not daily.exists():
        subprocess.run(["git", "init", "--quiet", daily], check=True)
        subprocess.run(["git", "-C", daily, "fetch", "--quiet", "--depth=1",
                        f"https://github.com/{DAILY_REPO}.git", DAILY_SHA], check=True)
        subprocess.run(["git", "-C", daily, "checkout", "--quiet", "--detach", "FETCH_HEAD"], check=True)
    assert subprocess.check_output(["git", "-C", daily, "rev-parse", "HEAD"], text=True).strip() == DAILY_SHA
    fetch_cache(root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    fetch(parser.parse_args().inputs)
