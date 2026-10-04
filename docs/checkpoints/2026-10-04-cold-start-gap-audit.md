# Exact first-entry evidence gap after parameter recovery

Continues `e1c7e8e41d15c89e7f6100da8b5b138ee48cfe3f`; no restart.

The recovered attack/DC/discipline parameters are intact. A read-only audit now
identifies all 46 missing rows by stable player/fixture identity, name, team,
position and the exact frozen v4 cutoff. All 46 have zero earlier 2025/26
observations, zero pre-cutoff registration evidence and zero pre-cutoff player
state snapshots in the recovered Core database. They affect 33 fixtures.

This is a data/contract gap, not missing numerical dependencies. The original
Phase 3C/3D/3E experiments require a nonempty current-season minutes state
(`sw>0`) before forecasting, so rerunning with the original parameters again
omits these players. Archive/member checksums and guard lines are saved in
`analysis/results/joint-cold-start-audit-v1/original-rule-evidence.json`.
The Phase 5X "manual cold start" concerns GW1–5 replay/chip decisions, not
first-entry component forecasts for later registrations.

Core registration/state tables contain 2023/24 and 2026/27 snapshots, but no
2025/26 rows. Retrospective merged-GW roster presence plus an invented deadline
timestamp cannot establish that a new player was registered before that
deadline. Earlier-season player history cannot substitute for the declared
current-season-only component contract.

Position shrinkage priors make a future first-entry model mathematically
possible without target fitting. Enabling that path is a separately versioned
component extension, requiring pre-cutoff roster/position evidence. Adding
attack propensities also changes within-team normalization: it must create a
new complete-roster paired input checkpoint, never patch the prior diagnostic.

## Validation and stopping condition

107 tests pass. Existing integrity passes 1,075 checks; the extended joint
checker passes 110 checks. Original simulator, frozen adapter, paired outputs
and transfer/chip sources are unchanged; policy hashes are recorded in
`analysis/results/joint-cold-start-audit-v1/verification.json`.

Full-roster/full-season replay remains blocked. No new holdout result or full
season replay is claimed. The prior paired diagnostic remains reproducible.

Next required evidence: archived 2025/26 predeadline FPL squad/registration
snapshots covering these first entrants, with source timestamps and identities;
player-state/prices and fixture/deadline horizons are also needed for full
season replay. Then implement an explicit first-entry component contract from
the frozen position priors and run a new paired control/v4 comparison with the
same common complete roster and unchanged transfer/chip strategy. Resolve the
already documented season-rules differences separately before full replay.

Reproduce:

```bash
PYTHONPATH=src python scripts/audit_joint_cold_start_gaps.py --out work/cold-start-audit-reproduced
PYTHONPATH=src python scripts/check_joint_checkpoint.py
PYTHONPATH=src python -m pytest -q tests
```

`missing_rows.csv`, `manifest.json` and `readiness.json` in the audit folder
contain the exact actionable inventory and input/output checksums.
