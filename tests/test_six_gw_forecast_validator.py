"""Regression tests for read-only six-GW historical forecast checks."""
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_six_gw_forecast import validate_forecasts


def _write(path, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["decision_gw", "gw", "id", "xpts_mean"])
        writer.writeheader()
        writer.writerows(rows)


def test_complete_two_gw_tail(tmp_path):
    p = tmp_path / "f.csv"
    _write(p, [
        {"decision_gw": 37, "gw": g, "id": player, "xpts_mean": 1.0}
        for g in (37, 38) for player in (1, 2)
    ] + [{"decision_gw": 38, "gw": 38, "id": 1, "xpts_mean": 2.0}])
    report = validate_forecasts(p, start=37, end=38)
    assert report["passed"]
    assert report["origin_target_pairs"] == report["required_pairs"] == 3


def test_missing_future_gw_is_blocking(tmp_path):
    p = tmp_path / "f.csv"
    _write(p, [{"decision_gw": 6, "gw": 6, "id": 1, "xpts_mean": 1.0}])
    report = validate_forecasts(p, start=6, end=6)
    assert not report["passed"]
    assert report["missing_origin_target_pairs"]["6"] == [7, 8, 9, 10, 11]


def test_missing_player_target_and_duplicates_are_blocking(tmp_path):
    p = tmp_path / "f.csv"
    rows = [{"decision_gw": 37, "gw": g, "id": player, "xpts_mean": 1.0}
            for g in (37, 38) for player in (1, 2)]
    rows = [r for r in rows if not (r["gw"] == 38 and r["id"] == 2)]
    rows.append(dict(rows[0]))
    _write(p, rows)
    report = validate_forecasts(p, start=37, end=37)
    assert not report["passed"]
    assert report["missing_origin_player_targets"]["37:38"]["count"] == 1
    assert any("duplicate" in x for x in report["structural_issues"])


def test_nonfinite_xp_is_rejected(tmp_path):
    p = tmp_path / "f.csv"
    _write(p, [{"decision_gw": 38, "gw": 38, "id": 1, "xpts_mean": "nan"}])
    assert not validate_forecasts(p, start=38, end=38)["passed"]
