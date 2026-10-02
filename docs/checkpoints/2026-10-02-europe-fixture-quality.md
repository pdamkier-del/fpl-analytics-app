# Europe-wide source identity audit

Continues the CL audit without replacing its frozen results. Organizer fixture
facts from UEFA add 189 Europa League and 153 Conference League proper fixtures.
These are retrospective identity inputs, not contemporaneous schedule state.
Source dates, teams, per-club scores, stages, URLs and source lines are frozen in
`data_v1_1/raw/independent-cup-inventory/uefa-el-conference-2025-26.csv` with SHA256
and provenance. Qualifiers are outside this organizer inventory.

The independent PL-club inventory has 29 EL and 15 Conference fixtures; source
has 28 EL keys (including two unfinished placeholders) and 13 Conference keys.
There are 39 unique pair/score matches and five unmatched reference fixtures.
The latter are join gaps, not an automatic missing-fixture count.

Two further date/score conflicts are confirmed: Forest/Midtjylland has an
October 2 kickoff but a score matching March 12; Palace/AEK Larnaca has an
October 23 kickoff but a 0-0 score matching March 12. Add 20 repeated-pair source
keys to the previous CL quarantine for 40 total. No knockout date is filled.
Accepted team-game rows are PL 760, CL 44, EL 13, Conference 5, EFL 52, with 12
incomplete mapped starting-XI stat records. FA Cup remains missing.

## Re-run with unchanged model protocol

Fit GW6–15, development GW16–21; final fit GW6–21 and **reused diagnostic**
GW22–38. C=1, Ridge alpha=20 and candidates unchanged. Development still selects
workload P(start) with original duration/cameo components.

| GW22–38, 13,987 rows | Brier | Log-loss | MAE | RMSE |
|---|---:|---:|---:|---:|
| V2 baseline | 0.077148 | 0.257716 | 11.958642 | 21.922479 |
| Reproducible role | 0.076645 | 0.251343 | 11.823680 | 21.858693 |
| PL-only workload | 0.075687 | 0.247169 | 11.669234 | 21.632280 |
| CL quarantine v2 | 0.075031 | 0.244203 | 11.462809 | 21.574454 |
| Europe quarantine v3 | 0.075016 | 0.244182 | 11.472713 | 21.571285 |
| Europe v3 full decomposition | 0.075016 | 0.244182 | 12.041601 | 21.465749 |

Role-control and PL-only predictions are exactly unchanged. This supports a
sensitivity check, not a new independent OOS claim or source certification.
Every variant reproduces saved inference with outcomes removed (start error
below 7e-16, minutes error below 6e-14). Metrics by GW/team/role are saved.

## Default safeguards and reproduction

The current feature builder defaults to the combined quarantine and a **new**
v3 output folder; it fails if the required audit file is absent. Omitting the
quarantine requires `--quarantine-csv '' --allow-unverified-cup-source`, an
explicit legacy-reproduction opt-in. Benchmark and inference CLI defaults use
v3 artifacts. Historical v1/v2 outputs are preserved.

```sh
python scripts/audit_independent_cl_fixtures.py
python scripts/audit_independent_europe_fixtures.py
python scripts/build_workload_features.py --db work/core.sqlite3
python scripts/benchmark_workload_minutes.py
python scripts/run_model_checks.py
python scripts/check_model_checkpoint.py --report analysis/results/checkpoint-readiness-europe-quality-20261002.json
```

No app model is activated and no full-season simulation is started. Complete
FA Cup/qualifier coverage, validated historical payloads/publication, as-of
competition snapshots, joint minutes/xP validation and replay integration remain.
