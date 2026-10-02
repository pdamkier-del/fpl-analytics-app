# Observed cup/Europe workload and minutes composition

Continues the published role/minutes foundation on the same model branch.
Historical Core, q/H, CAM, the original V2 baseline and the existing app/UI are
preserved. This adds observed workload rather than restarting the model.

## Source and cutoff audit

Frozen external data source: `olbauday/FPL-Core-Insights`, commit
`bfcc14deaaa924157eee1d60f33a898cbd64404e`. This is a data source, not our model
repository. 115 raw files are preserved under
`data_v1_1/raw/all-competitions-2025-26/`; SOURCE_MANIFEST records the exact
Git blob hashes. All 115 downloaded files match those source blobs.

There are 525 unique source matches: 380 PL, 40 EFL Cup, 64 Champions League,
28 Europa League and 13 Conference League. **FA Cup is absent.** In addition,
36 cup/Europe matches have missing kickoff timestamps and four are not finished
according to source labels. They are excluded, with explicit reasons: a GW
assignment is not enough to establish historical availability. Non-PL opponent
sides are excluded from the PL-club ledger. Missing lineups or minutes do not
become zero-minute observations.

The accepted team-match ledger has 760 PL, 52 EFL Cup, 48 CL, 14 EL and six
Conference League records. Thirteen non-PL team records have incomplete mapped
starting-XI stats. This is a verified **observed subset**, not a certified
complete all-official-match inventory. International matches and pre-season
friendlies are excluded; workload from a previous club is not yet carried
across transfers.

European lineups frequently have blank FPL IDs although player-minute stats
have valid FPL IDs. 1,313 lineup rows are resolved only through an exact unique
club-code/display-name alias witnessed in PL lineups. No fuzzy matching or
cross-club name matching is used. The resolution CSV is retained. This is
retrospective stable identity linkage, not future outcome data as a feature.

All 38 FPL deadlines exist in the source. GW6–38 match the old proxy cutoff
timestamps exactly, so previous numerical results do not change. These are
authoritative FPL deadline values mirrored by the source. Actual publication
times for outcomes remain unavailable: kickoff+3h is still a reconstruction
proxy, and cohort/schedule ingestion is not certified.

## Workload features

`src/fpl_v1_1_model/workload.py` builds, strictly from games available before
cutoff: player minutes over 7/14/28 days; starts over 7/14 days; minute mass
with fixed calendar half-lives of three/seven days; player rest/missing-history;
team matches over 7/14 days, non-PL matches over seven days, team rest and
incomplete player-stat coverage over 14 days. Extra-time minutes up to 120
are retained for workload; projected PL minutes remain bounded by 90.

Workload is separate from Match Importance. Unknown player exposure has an
explicit missing-history flag. The features do not assert that a missing
observation means the player did not play. All-competition completeness is
false on every prediction row. PL-only features are saved as an ablation.

## Minutes-error composition

`scripts/audit_minutes_composition.py` attributes the previous full-decomposition
MAE/MSE difference across all six replacement orders (exact Shapley average).
MAE contribution: start duration +0.294945, sub probability +0.281869, sub
duration +0.070076 minutes; total +0.646890. MSE contributions are −3.983059,
+1.286415 and −2.938183; total −5.634827. Identities hold for every row.

63.42% of this roster has zero actual minutes. A conditional mean minimizes
MSE, whereas a conditional median minimizes MAE; pushing E[min] toward zero
solely to improve MAE need not improve expected points. This is an objective
distinction, not a causal proof for all errors. Prediction-bin calibration and
event/role-impact contributions are saved. All analyses are posthoc diagnostics.

## Development validation and frozen diagnostic

Training: GW6–15; validation: GW16–21 (4,670 rows). All start models are
refitted on development-training labels only, never the role model already
fitted through GW21. Final fits use GW6–21 and freeze coefficients/scalers.
Fixed C=1 logistic and alpha=20 Ridge are inherited, not searched against the
old reported figures. There was no hyperparameter optimization.

Start selection uses development log-loss. For this new expected-mean experiment,
minutes selection uses development RMSE, with MAE and bias also reported.
This objective differs explicitly from the previous squad experiment's MAE
selection and reflects the known conditional-mean issue. It is not a new blind
preregistered experiment. PL-only was added as an explanatory ablation and is
excluded from candidate selection. No candidate is promoted into the app.

| Development GW16–21 | Brier | Log-loss | xMins MAE | RMSE |
|---|---:|---:|---:|---:|
| Role control, old minutes | 0.077405 | 0.256518 | 12.128577 | 22.006631 |
| Workload start, old minutes | 0.075504 | 0.247007 | 11.429463 | 21.727320 |
| Role start, new decomposition | 0.077405 | 0.256518 | 12.813287 | 21.995981 |
| Workload start, new decomposition | 0.075504 | 0.247007 | 11.986542 | 21.807029 |
| PL-only start ablation, old minutes | 0.075509 | 0.246789 | 11.616899 | 21.757830 |

Development selects workload P(start) with the existing conditional minutes.
It also wins MAE among the four candidates. The new full decomposition is not
selected. It remains saved for future joint/xP validation.

GW22–38 has already been repeatedly inspected. These 13,987 aligned rows are
**reused diagnostic**, not a fresh independent OOS confirmation:

| GW22–38 reused diagnostic | Brier | Log-loss | xMins MAE | RMSE |
|---|---:|---:|---:|---:|
| Original V2 comparator | 0.077148 | 0.257716 | 11.958642 | 21.922479 |
| Role control | 0.076645 | 0.251343 | 11.823680 | 21.858693 |
| Workload start, old minutes | 0.075038 | 0.244250 | 11.457621 | 21.577277 |
| Role start, new decomposition | 0.076645 | 0.251343 | 12.470570 | 21.729419 |
| Workload start, new decomposition | 0.075038 | 0.244250 | 12.020507 | 21.470246 |
| PL-only start ablation | 0.075687 | 0.247169 | 11.669234 | 21.632280 |

Observed cup/Europe inputs improve the reused diagnostic relative to PL-only,
but development log-loss is slightly worse (0.247007 vs 0.246789). Development
MAE/RMSE are better. Thus this is promising partial-coverage evidence, not
proof that the source is complete or that European workload universally helps.

Against role control, workload improves 15/17 GWs in Brier, 16/17 in log-loss,
MAE and RMSE; 16/20 teams in Brier, 18/20 in log-loss, 20/20 in MAE and 17/20
in RMSE. In the cutoff-safe high-role-impact group, MAE improves 26.546922→
26.037033 (n=1,994), but log-loss marginally worsens. For rows with an observed
non-PL team match in the previous seven days, MAE improves 13.885519→13.040460
(n=1,117). Grouping is by historical inputs, not current actual starter roles.
Results per GW/team/expected-role/target disagreement and components are saved.

## Reproduction and checkpoint integrity

```bash
python scripts/restore_core_checkpoint.py
python scripts/audit_minutes_composition.py
python scripts/build_workload_features.py --db work/core.sqlite3
python scripts/benchmark_workload_minutes.py
python scripts/check_model_checkpoint.py --report analysis/results/checkpoint-readiness-20261002.json
python scripts/run_model_checks.py
```

`requirements-model-checkpoint.txt` pins the numerical environment used.
`workload-v1/` contains the official-minute ledger, coverage/exclusions/identity
resolutions, verified deadlines, full q/H+workload features and checksums.
`workload-minutes-v1/` contains model input columns and keyed predictions,
development/frozen coefficients/scalers, metrics, selection protocol and
checksums. Full q/H can be joined by fixture/player to the immutable input
feature file recorded in the manifest. Gzip writers are atomic and validated.

The new integrity checker checks all six current experiment manifests and all
frozen source blob hashes. It detects truncated gzip even when a file exists.
It does not overwrite benchmarks or conflate integrity with deployment readiness.
The initial 42 assertion tests pass. A separate rebuild reproduces all seven workload and
13 workload-benchmark outputs byte-for-byte (manifests excluded because the
second run intentionally references a different input path). The integrity
report initially verifies 366 manifest references, 312 unique files and all 115 raw blobs.

## Standalone forecast adapter

`src/fpl_v1_1_model/frozen_forecast.py` performs inference from serialized
coefficients/scalers without sklearn estimators or outcome columns. It accepts
only declared model inputs, checks history-before-cutoff and fit cutoff, and
requires a full unique roster per fixture/team/cutoff. It keeps repeated
forecasts at different cutoffs separate. It emits all minutes components and
the expected-minutes identity, explicitly marked experimental/partial coverage.

Outcome-free inference validation exposed and fixed an export-key collision:
start probability and start duration originally both used `*_start`. They now
use `*_start_probability` and `*_start_duration`. The first export omitted the
probability coefficients; the benchmark prediction calculations were unaffected.
The corrected export keeps every model. Both prediction files remain byte-identical.

The benchmark now verifies standalone predictions for all 13,987 diagnostic
rows, all five variants, after removing all outcome/posthoc columns. Errors
must be below 1e-10 for probability and 1e-9 minutes; a verification JSON and
code checksums are saved. 45 assertion tests pass, including future-data,
pre-training-cutoff and duplicate/partial-roster rejection.

For an outcome-free feature CSV whose cutoffs follow the frozen fit:

```bash
python scripts/predict_frozen_workload.py --features work/forecast_features.csv.gz --out work/experimental_forecasts.csv.gz
```

This supplies a tested standalone model-to-forecast adapter. A live feature
builder, certified availability/cohort inputs and app/replay integration still
remain; the active desktop engine is not silently switched.

Before the requested full season simulation, remaining work is complete cup
coverage, as-of schedule/active-competition/stage history for Match Importance,
joint squad/sub/duration validation, a new independent test period and an app/
forecast/replay adapter. The frozen V2 already contains dynamic competition-value
and hierarchy-importance functions; those should be reused, not replaced by a
team-wide additive importance score. Future elimination results must never be
used to infer a team's earlier active competition set. No full-model season
simulation or importance/cup-value fitting is claimed at this checkpoint.
