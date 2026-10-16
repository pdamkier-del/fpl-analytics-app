#!/usr/bin/env python3
"""Single offline entry point for the already connected individual MM + PM v2.

No production flags, forecast pages, locked parameters or benchmarks are changed.
Uses the existing fixed-75 PM v2 and the experimental start/survival MM under
the legal joint-XI simulator. Also replays locked controls for valid A/B.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "scripts" / "research_dynamic_pm_v2.py"
RUNTIME = ROOT / "scripts" / "locked_numerical_runtime.py"
DATA = ROOT / "work" / "dynamic-source"
RESULTS = ROOT / "analysis" / "results" / "dynamic-pm-v2-20261015"
ARMS = (("locked", "independent"), ("locked", "legal"), ("mm", "legal"))
SEASONS = ("2024-25", "2025-26")


def commands(shards):
    prefix = [sys.executable, str(RUNTIME), str(WORKER)]
    yield prefix + ["--stage", "select"]
    for season in SEASONS:
        for mm, layout in ARMS:
            for shard in range(shards):
                yield prefix + [
                    "--stage", "replay", "--season", season,
                    "--mm", mm, "--layout", layout,
                    "--shards", str(shards), "--shard", str(shard),
                ]
    yield prefix + ["--stage", "aggregate", "--shards", str(shards)]


def preflight():
    missing = [str(p) for p in (WORKER, RUNTIME, DATA, ROOT / "work" / "core.sqlite3") if not p.exists()]
    source_files = list(DATA.rglob("*_inputs.jsonl.gz")) if DATA.is_dir() else []
    if len(source_files) < 16:
        missing.append("at least 16 restored *_inputs.jsonl.gz captures under work/dynamic-source")
    return missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="Run complete historical research matrix")
    ap.add_argument("--shards", type=int, default=6)
    args = ap.parse_args()
    if args.shards < 1:
        ap.error("shards must be positive")
    plan = list(commands(args.shards))
    print(json.dumps({
        "classification": "OFFLINE_MM_PM_V2_LEGAL_XI",
        "production_modified": False,
        "locked_model_active": False,
        "promotion_allowed": False,
        "seasons": SEASONS,
        "arms": ARMS,
        "matrix_commands": len(plan),
        "data_gaps": preflight(),
        "results": str(RESULTS),
    }, indent=2))
    if not args.run:
        return 0
    missing = preflight()
    if missing:
        print("Cannot run: " + "; ".join(missing), file=sys.stderr)
        return 2
    for i, cmd in enumerate(plan, 1):
        print(f"Combined MM/PM v2 step {i}/{len(plan)}: {' '.join(cmd)}", flush=True)
        subprocess.run(cmd, cwd=ROOT, check=True)
    summary = RESULTS / "summary.json"
    if not summary.is_file():
        raise RuntimeError("Matrix finished without verified summary.json")
    report = json.loads(summary.read_text())
    for season in SEASONS:
        for mm, layout in ARMS:
            if mm + "_" + layout not in report.get(season, {}):
                raise RuntimeError(f"Missing {season} {mm}/{layout} result")
    print("Full combined offline matrix complete; not production approved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
