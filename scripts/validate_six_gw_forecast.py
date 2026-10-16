#!/usr/bin/env python3
"""Read-only validator for six-GW historical forecast inputs.

Does not generate forecasts, repair missing values, alter TS, or use outcomes.
Run on a saved origin/target/player forecast CSV(.gz) before a TS replay.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path


def validate_forecasts(path, start=6, end=38, horizon=6, strict_players=True):
    if not (1 <= start <= end <= 38 and 1 <= horizon <= 38):
        raise ValueError("Invalid GW range or horizon")
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    by_origin = defaultdict(lambda: defaultdict(dict))
    issues = []
    count = 0
    with opener(path, "rt", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        needed = {"decision_gw", "gw", "id", "xpts_mean"}
        if not needed.issubset(reader.fieldnames or ()):
            raise ValueError(f"Missing required columns: {sorted(needed - set(reader.fieldnames or ())) }")
        for line, row in enumerate(reader, start=2):
            count += 1
            try:
                origin = int(row["decision_gw"])
                target = int(row["gw"])
                player = int(row["id"])
                xp = float(row["xpts_mean"])
                if not math.isfinite(xp):
                    raise ValueError("nonfinite xP")
                if player <= 0:
                    raise ValueError("invalid player id")
                if origin < start or origin > end:
                    issues.append(f"line {line}: origin GW{origin} outside requested range")
                    continue
                if not origin <= target <= min(38, origin + horizon - 1):
                    issues.append(f"line {line}: target GW{target} outside GW{origin} horizon")
                    continue
                if player in by_origin[origin][target]:
                    issues.append(f"line {line}: duplicate GW{origin}->GW{target} player {player}")
                by_origin[origin][target][player] = xp
            except (ValueError, TypeError, KeyError) as exc:
                issues.append(f"line {line}: malformed forecast: {exc}")

    cells = 0
    expected = 0
    missing_pairs = {}
    missing_players = {}
    for origin in range(start, end + 1):
        required = set(range(origin, min(38, origin + horizon - 1) + 1))
        expected += len(required)
        observed = {g for g, players in by_origin[origin].items() if players}
        cells += len(observed & required)
        absent = sorted(required - observed)
        if absent:
            missing_pairs[str(origin)] = absent
        # A player known at the decision GW must have a row for every target.
        # This is a diagnostic proxy for squad coverage; an authoritative
        # deadline-eligible player list is still required for certification.
        universe = set(by_origin[origin].get(origin, {}))
        for target in sorted(required):
            if universe and target in by_origin[origin]:
                missing = sorted(universe - set(by_origin[origin][target]))
                if missing:
                    missing_players[f"{origin}:{target}"] = {
                        "count": len(missing), "examples": missing[:20]
                    }
    blockers = bool(issues or missing_pairs or (strict_players and missing_players))
    return {
        "classification": "INPUT_CONTRACT_ONLY_NOT_TS_CERTIFICATION",
        "input": str(path),
        "rows": count,
        "origins_required": end - start + 1,
        "origin_target_pairs": cells,
        "required_pairs": expected,
        "missing_origin_target_pairs": missing_pairs,
        "missing_origin_player_targets": missing_players,
        "structural_issues": issues[:200],
        "truncated_issue_count": max(0, len(issues) - 200),
        "strict_players": strict_players,
        "passed": not blockers,
        "caveats": [
            "Passing checks structural coverage, not deadline-safe source publication times.",
            "Player coverage is inferred from each origin's first target; verify against an authoritative deadline roster.",
            "A forecast generated with reused future MM state is not a true forward MM forecast.",
            "Do not interpret passing as a comparable six-GW TS replay or production approval.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("forecast", help="origin/target/player CSV or CSV.gz")
    parser.add_argument("--start", type=int, default=6)
    parser.add_argument("--end", type=int, default=38)
    parser.add_argument("--horizon", type=int, default=6)
    parser.add_argument("--allow-player-gaps", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate_forecasts(args.forecast, args.start, args.end, args.horizon,
                                strict_players=not args.allow_player_gaps)
    payload = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload)
    print(payload, end="")
    raise SystemExit(0 if report["passed"] else 2)


if __name__ == "__main__":
    main()
