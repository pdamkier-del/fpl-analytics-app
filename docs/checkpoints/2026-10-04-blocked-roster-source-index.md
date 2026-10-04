# Pinned inventory for the remaining roster source gap

Continues cc682afe9777925a9adaef06ddaec5d53e66e44a. The previous paired replay is complete; no forecast or policy is changed.

Recovered all five January–May 2026 month trees from the same pinned Randdalf/fplcache commit used by the deadline snapshots. The compressed Git tree inventory and its checksums are preserved in blocked-roster-source-index-v1. The source audit and checker prepare a separate forensic bracket for the 32 blocked rows; source bytes and the finished report follow in the next checkpoint.

To restore the audit inventory into a fresh workspace:

```sh
mkdir -p work/roster-gap-source
python -c "import gzip,pathlib; pathlib.Path('work/roster-gap-source/trees.json').write_bytes(gzip.decompress(pathlib.Path('analysis/results/blocked-roster-source-index-v1/trees.json.gz').read_bytes()))"
PYTHONPATH=src python scripts/audit_blocked_roster_near_deadline.py --out work/blocked-roster-bracket-reproduced
```

Uses the existing read-only recovered Core. All postdeadline source states are evidence about the gap, never eligible model inputs. Keep old predictions, policies and the 144-fixture controlled cohort untouched.
