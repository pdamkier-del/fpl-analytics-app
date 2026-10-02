# Squad/bench development validation

Continues the existing role/minutes checkpoint. The frozen earlier results are
unchanged. All 760 team-fixtures were audited: 747 have complete 20-player
lineups; four list only starters. Negative squad labels require complete lists
without detected contradictions. Unknown membership is never an injury label.
282 of 26,159 feature-cohort squad labels remain unknown and are not converted
to negatives. Only historical matches completed before cutoff enter features.

The new probability decomposition is:
P(sub|not start) = P(squad|not start) * P(sub|confirmed bench).
P(squad) = P(start) + (1-P(start))*P(squad|not start), so it cannot fall below
P(start). This is squad selection, not medically available/unavailable status.

Fit GW6-15; validate GW16-21 (4,670 rows). Crucially, the role-aware start
model is refitted only on the development-training period: its GW6-21 fitted
predictions are not used to choose minutes components on GW16-21.

| Development variant | xMins MAE | RMSE |
|---|---:|---:|
| Existing conditional-minutes control | 12.128577 | 22.006631 |
| Factorized squad/sub, existing durations | 12.325191 | 22.041910 |
| Factorized squad/sub, new durations | 12.643937 | 21.908237 |

Predeclared selection objective is MAE, with control winning ties. Development
selects the existing conditional-minutes control. This is not a holdout-based
choice. Models/candidates/hyperparameters and training cutoffs are saved.

Refit GW6-21, then report already inspected GW22-38 as **reused diagnostic**,
not fresh independent OOS:

| Variant | xMins MAE | RMSE |
|---|---:|---:|
| Control | 11.823680 | 21.858693 |
| Factorized sub | 12.009788 | 21.838360 |
| Factorized full | 12.331233 | 21.628575 |

Start Brier/log-loss remain 0.076644975556 / 0.251342578244. No new candidate
is promoted into the app. Match Importance/cup-value remains untouched.

Reproduce with `python scripts/benchmark_squad_minutes.py --db work/core.sqlite3`.
Outputs under `analysis/results/squad-minutes-v1/` include coverage, labels,
pre-cutoff features, development and diagnostic predictions, coefficients,
selection protocol and input/code/output checksums. 37 assertion tests passed.

## Connector publication storage

The connector could upload ordinary checkpoint files (including 8.2 MB gzip
predictions) but rejected the 42.9 MB compressed SQLite transport request.
The unchanged gzip is therefore stored as six lossless byte parts under
`model/checkpoints/phase5e_core/parts/`, with `PARTS_MANIFEST.json` validating
every part, the original compressed file and decompressed SQLite. No data has
been omitted. Restore with `python scripts/restore_core_checkpoint.py`.
The original 42.9 MB local gzip remains on disk, but is not tracked at HEAD.
Earlier local commits containing it are preserved; connector-replayed commits
defer that file to the final split-storage commit. A temporary CSV writer file
is also omitted from published intermediate history. All final tracked files
must have identical local/GitHub tree hashes. Publication mapping is recorded
separately. The active app/UI is unchanged.
