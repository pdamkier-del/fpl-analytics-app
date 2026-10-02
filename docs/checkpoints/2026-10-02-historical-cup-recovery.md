# Original cup payload recovery and workload v4

Continues the Europe quarantine checkpoint, preserving all v1/v2/v3 artifacts.
Seven original league-phase team-games and 104 player-minute observations are
recovered from historical Git source versions. Current ambiguous rows remain
quarantined; recovery uses separate fixture keys containing competition, date
and actual organizer home/away teams. No current payload is moved to a new date.

## What the version diff proves

All seven recovered games have exactly unchanged player membership, minutes
and goals in the later player-stat files. The source match table has changed
scores/fixture metadata under several of those same keys. This demonstrates
mixed table versions, **not** future player-minute contamination in these seven
cases. The earlier risk assessment was conservative; the direct version diff
now narrows it. Comparable known start labels also have zero changes. Villa/
Bologna and Forest/Porto have no mapped current lineup entries for their 11
original starters, explaining why current-lineup-only ingestion loses them.
The remaining ambiguous source keys are not certified by this limited diff.

The pre-knockout snapshot (`2c00c3886c421d488ff017d83e96631474b80847`, February 9)
locates eight original rows. Source GW assignment changed between versions:
the original chronological GW5/6/7/9/16 folders became GW4/5/6/8/15 in a later
rebucketing. Never use the folder GW as a kickoff or availability timestamp.
Palace/AEK Larnaca is not present in the selected earlier bounded snapshots and
is not recovered. Its February version is retained for audit only.

## Cutoff and missing-label rules

Each restored fixture must uniquely match the independent organizer club pair,
per-club score and calendar date. CL kickoff clocks must additionally match the
independent inventory. A source version preceding kickoff is rejected.

`available_at = max(kickoff + 3 hours, recorded source Git version timestamp)`.
This is more conservative than assigning availability from kickoff alone; the
Git timestamp is a recorded version boundary, not an exact ingestion guarantee.
All cutoffs still come from the 38 authoritative FPL deadlines. GW7 and GW9 had
Friday deadlines. Earlier Friday snapshots recover Liverpool and Arsenal data;
Forest/Midtjylland and Forest/Porto lack a complete selected earlier version and
use later snapshots. Those later records cannot enter the Friday forecasts.
Boundary tests reject history at or after cutoff and preserve unknown states.

Historical lineup files are absent. Valid player interval endpoints identify
six complete starting XIs. City/Real has unusable all-zero start intervals, so
all 15 City start labels remain NULL; its 990 total observed minutes are kept.
No unknown player is treated as absent and no missing minute is set to zero.

Coverage: PL 760, CL 48, EL 16, Conference 5 and EFL 52 team-game rows. There
are 13 incomplete starting-XI/stat records. FA Cup, qualifiers and remaining
European knockout observations remain incomplete. This is not a complete
all-official-match workload dataset.

## Fixed-protocol validation

Train GW6–15/development GW16–21, final fit GW6–21, same C=1/alpha=20/candidates.
GW22–38 remains a **reused diagnostic**, 13,987 rows, not independent OOS.

| Diagnostic model | Brier | Log-loss | xMins MAE | xMins RMSE |
|---|---:|---:|---:|---:|
| V2 baseline | 0.077148 | 0.257716 | 11.958642 | 21.922479 |
| Reproducible role | 0.076645 | 0.251343 | 11.823680 | 21.858693 |
| PL-only workload | 0.075687 | 0.247169 | 11.669234 | 21.632280 |
| Europe quarantine v3 | 0.075016 | 0.244182 | 11.472713 | 21.571285 |
| Recovered originals v4 | 0.075063 | 0.244381 | 11.473759 | 21.583163 |
| v4 full minutes decomposition | 0.075063 | 0.244381 | 12.038701 | 21.472820 |

Restoration slightly worsens the reused metrics versus quarantine-only v3;
it is retained for source correctness. Role control and PL-only forecasts are
exactly unchanged. Development workload P(start) log-loss is 0.247174 versus
role control 0.256518; PL-only is better at 0.246789. The PL-only diagnostic
ablation remains outside the pre-existing candidate-selection protocol. Thus
these results do not establish a robust incremental benefit from cup data.
The four-candidate protocol still selects workload start with old conditional
durations; full decomposition is not selected. No tuning targets old reported
role-aware scores or the restoration's diagnostic metrics.

## Reproduction and persistence

```sh
python scripts/restore_core_checkpoint.py
python scripts/audit_independent_cl_fixtures.py
python scripts/audit_independent_europe_fixtures.py
python scripts/recover_historical_cup_workload.py --db work/core.sqlite3
python scripts/audit_historical_cup_payload_versions.py
python scripts/build_workload_features.py --db work/core.sqlite3
python scripts/benchmark_workload_minutes.py
python scripts/run_model_checks.py
python scripts/check_model_checkpoint.py --report analysis/results/checkpoint-readiness-recovered-cups-20261002.json
```

Current builder/benchmark/inference CLI defaults use v4. For quarantine-only
reproduction use `--restored-workload ''` with explicit output and feature paths.
Legacy unverified reproduction additionally requires an empty quarantine plus
`--allow-unverified-cup-source`. Restoration without quarantining the original
source IDs fails, preventing double-counting the same physical games.

Manifests preserve every input, builder/classifier code version and output SHA.
The checkpoint checker verifies 1,075 manifest references, 115 original raw Git
blobs, 67 historical raw Git blobs and the independent CL Git blob. The UEFA
organizer-facts CSV has its own SHA256 provenance. All 61 assertion tests pass.
The historical raw source packs retain explored snapshots as well as selected
ones; only `deadline-cup-source-2025-26` enters the recovery builder. Exploration
files are not forecast features.

App/UI and main remain preserved. No full-season simulation or Match Importance
fit is started. Remaining work: FA Cup/qualifier/knockout player coverage, as-of
competition-state snapshots, joint squad/minutes/xP validation, a fresh test
period, and existing app/replay integration.
