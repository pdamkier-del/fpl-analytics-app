# Cup fixture identity quarantine checkpoint

The immutable original workload experiment remains available, but its non-PL
source payloads are not certified cutoff-safe. An independent frozen CL inventory
exposes three source rows whose existing kickoff agrees with an early fixture
while their score uniquely matches a later meeting. This is evidence of fixture
identity collisions or payload replacement; exact overwrite history is unproven.
The source uses date-free club-pair keys. Never infer a fixture from an H2H URL.

## Independent inventory and quarantine

The 189-match inventory contains 69 CL fixtures involving PL clubs. The original
source has 64 CL keys: 61 unique club-pair/per-club-score matches and three
ambiguous matches. Eight reference fixtures are unmatched by that unique-score
join, which does **not** prove eight missing fixtures. Of 47 supplied timestamp
anchors, three disagree. The undeclared timezone recovery gate therefore fails;
no kickoff is filled. Fourteen missing-date candidates remain diagnostic only.

Conflicts: Barcelona/Newcastle (source September 18, score matches March 10),
Manchester City/Real Madrid (source December 10, score matches March 11), and
Atlético/Arsenal (source October 21, score matches May 5). These are season
2025/26 dates. All 20 CL source keys for club pairs appearing more than once in
the inventory are quarantined, including four previously accepted dated games.
Accepted CL team-game rows decrease from 48 to 44. Unknown coverage remains
unknown; no minutes are filled with zero and no source file is rewritten.

## Fixed-protocol re-run

Same features, C=1, Ridge alpha=20, fit GW6–15/development GW16–21; final fit
GW6–21 and **reused diagnostic** GW22–38, 13,987 rows. No tuning towards old
reported metrics. Development selects workload P(start) with the original
conditional-minute components for both log-loss and xMins RMSE.

| GW22–38 diagnostic | Brier | Log-loss | xMins MAE | xMins RMSE |
|---|---:|---:|---:|---:|
| V2 baseline | 0.077148 | 0.257716 | 11.958642 | 21.922479 |
| Reproducible role control | 0.076645 | 0.251343 | 11.823680 | 21.858693 |
| PL-only workload | 0.075687 | 0.247169 | 11.669234 | 21.632280 |
| Original cup-source workload v1 | 0.075038 | 0.244250 | 11.457621 | 21.577277 |
| Quarantined workload v2 | 0.075031 | 0.244203 | 11.462809 | 21.574454 |
| Quarantined full decomposition | 0.075031 | 0.244203 | 12.032434 | 21.468962 |

Quarantine changes selected-model MAE by +0.005188 minutes and RMSE by
−0.002824. PL-only predictions remain exactly unchanged. The apparent workload
gain survives this sensitivity check; remaining cup coverage and publication
uncertainty prevent certification. Full decomposition still worsens MAE; it is
not selected or activated. All metrics by GW/team/role and inference replay
verification are saved under `analysis/results/workload-quality-minutes-v2`.

## Reproduction

```sh
python scripts/audit_independent_cl_fixtures.py
python scripts/build_workload_features.py --db work/core.sqlite3 --quarantine-csv analysis/results/independent-cl-audit/workload_quarantine.csv --out analysis/results/workload-quality-v2
python scripts/benchmark_workload_minutes.py --features analysis/results/workload-quality-v2/all_features.csv.gz --out analysis/results/workload-quality-minutes-v2
python scripts/run_model_checks.py
python scripts/check_model_checkpoint.py --report analysis/results/checkpoint-readiness-cup-quality-20261002.json
```

Restore Core first with `scripts/restore_core_checkpoint.py` when necessary.
Inputs, code and outputs have SHA256 manifests; the independent TXT preserves
the exact Git source blob and immutable source commit. Old experiment code
checks may resolve the recorded bytes from Git history, while all input/output
checks remain strict against saved files. Reproduce an old experiment from its
recorded historical code commit, not the current builder.

The app/UI and main branch are preserved. Match Importance and full-season
simulation remain blocked on complete cup/Europe fixture identity, historical
schedule/state snapshots, joint squad/minutes/xP validation, a fresh independent
test period, and app/replay integration. No full-season simulation has started.
