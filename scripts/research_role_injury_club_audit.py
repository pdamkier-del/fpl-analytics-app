"""Research-only, deadline-aware injury/role evidence and team error audit.

Evidence is append-only. A missing report NEVER means healthy, and a
post-deadline observation NEVER enters the forecast. No synthetic injuries.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from collections import defaultdict
from statistics import mean
import csv
import json
import math
from pathlib import Path

STATES = {"OUT", "DOUBTFUL", "RETURNING", "AVAILABLE", "UNKNOWN", "SUSPENDED"}
RANK = {"UNKNOWN": 0, "AVAILABLE": 1, "RETURNING": 2, "DOUBTFUL": 3,
        "OUT": 4, "SUSPENDED": 4}

def instant(s):
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("Timestamp must carry timezone")
    return d.astimezone(timezone.utc)

@dataclass(frozen=True)
class Evidence:
    player_uuid: str
    club_id: str
    effective_at: str
    published_at: str
    captured_at: str
    source_url: str
    source_kind: str
    state: str
    return_earliest: str = ""
    return_latest: str = ""
    injury_type: str = ""
    training_state: str = ""
    confidence: str = "unverified"

    def validate(self):
        if not self.player_uuid or not self.club_id or not self.source_url:
            raise ValueError("Missing identity, club or source")
        if self.state not in STATES:
            raise ValueError("Unrecognized status")
        for key in ("effective_at", "published_at", "captured_at"):
            instant(getattr(self, key))
        if instant(self.published_at) > instant(self.captured_at):
            raise ValueError("Capture precedes publication")
        if self.return_earliest and self.return_latest:
            if instant(self.return_earliest) > instant(self.return_latest):
                raise ValueError("Reversed return window")
        if self.confidence not in ("official", "reported", "unverified"):
            raise ValueError("Invalid provenance")
        return self

def asof_status(records, cutoff, player_uuid):
    """Last time-visible observation; unresolved same-clock conflicts → UNKNOWN."""
    cut = instant(cutoff)
    visible = [r.validate() for r in records
               if r.player_uuid == player_uuid
               and max(instant(r.published_at), instant(r.captured_at)) < cut
               and instant(r.effective_at) <= cut]
    if not visible:
        return {"state": "UNKNOWN", "evidence": 0, "source": None}
    priority = {"official": 2, "reported": 1, "unverified": 0}
    # Most recent captured information wins; source credibility breaks exact ties.
    visible.sort(key=lambda r: (instant(r.captured_at), priority[r.confidence]))
    latest = visible[-1]
    tied = [r for r in visible if
            (instant(r.captured_at), priority[r.confidence]) ==
            (instant(latest.captured_at), priority[latest.confidence])]
    if len({r.state for r in tied}) > 1:
        return {"state": "UNKNOWN", "evidence": len(visible), "source": None,
                "conflict": True}
    return {"state": latest.state, "evidence": len(visible),
            "source": latest.source_url, "confidence": latest.confidence,
            "return_earliest": latest.return_earliest,
            "return_latest": latest.return_latest,
            "injury_type": latest.injury_type, "training_state": latest.training_state}

def load_evidence(path):
    p = Path(path)
    with p.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [Evidence(**row).validate() for row in rows]

def club_error_report(rows):
    """Evaluate paired row-wise minutes; skip rows without verified actuals.

    Required row keys: season, club, player_uuid, fixture_uuid, actual_minutes,
    baseline_minutes, candidate_minutes. This is a diagnostic, not model fitting.
    """
    by = defaultdict(list)
    seen = set()
    for r in rows:
        key = (r["season"], r["fixture_uuid"], r["player_uuid"])
        if key in seen:
            raise ValueError("Duplicate scored player fixture")
        seen.add(key)
        values = [float(r[k]) for k in
                  ("actual_minutes", "baseline_minutes", "candidate_minutes")]
        if not all(math.isfinite(v) and 0 <= v <= 90 for v in values):
            raise ValueError("Invalid minute observations")
        by[(r["season"], r["club"])].append(values)
    out = []
    for (season, club), values in sorted(by.items()):
        base = mean(abs(y-b) for y,b,c in values)
        candidate = mean(abs(y-c) for y,b,c in values)
        out.append(dict(season=season, club=club, n=len(values),
                        original_mae=base, candidate_mae=candidate,
                        delta_mae=candidate-base,
                        original_bias=mean(b-y for y,b,c in values),
                        candidate_bias=mean(c-y for y,b,c in values)))
    return sorted(out, key=lambda x: (-x["delta_mae"],x["season"],x["club"]))

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--paired-csv", required=True)
    p.add_argument("--output-json", required=True)
    args = p.parse_args()
    with open(args.paired_csv, newline="", encoding="utf-8") as f:
        result=club_error_report(csv.DictReader(f))
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    for r in result:
        print(f"{r['season']} {r['club']}: n={r['n']} baseline={r['original_mae']:.3f} new={r['candidate_mae']:.3f} delta={r['delta_mae']:+.3f}")

if __name__ == "__main__":
    main()
