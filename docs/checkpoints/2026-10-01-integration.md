# Standing model integration and CAM checkpoint

The model was recovered and integrated into the existing repository, not rebuilt.
The original app/frontend/bridge engine is unchanged. This branch is experimental
and is not a promoted forecasting model.

## Provenance and components

The supplied standing V2 archive has 20 manifest entries; all SHA-256 hashes
were verified. Its original files are preserved under
`model/checkpoints/role_aware_standing_v2`. Working copies are in `src`, `scripts`
and `tests`. Archive hashes are recorded in `model/checkpoints/provenance.json`.

| Component | Recovery |
| --- | --- |
| Historical Core | Existing Phase 5E database, stored immutably as gzip; no final duplicate player/fixture keys |
| Database source SHA-256 | a4742428fb0c9943ff3ee565f765eb98d733a1690180c566d6df794786ef409f |
| Historical player observations | 2022/23: 26,505; 2023/24: 29,725; 2024/25: 27,283; 2025/26: 29,747 |
| Lineups/formations/average positions | 114 existing-source CSVs downloaded; 380 matches, 15,153 lineup rows, 8,360 starters, 11,448 position rows |
| Detailed source | olbauday/FPL-Core-Insights, 2025-2026 Premier League; exact downloaded bytes recorded in SHA256_MANIFEST.json |
| Importer | Existing formation + coarse-position + geometric importer, plus explicit CAM and separate GK repair |
| q/H | Existing recency-weighted role minutes and role hierarchy builder; CAM is a canonical role |
| P(start) | Recovered standing pstart_v2 module with constrained transport and deadline availability/registration |
| Minutes | Existing Phase 5E minutes.py restored, including starter/cameo decomposition |
| Cutoff state | Existing state lookup code preserved; supplied archive contains summary audits, not the original cutoff database |
| Tests | 11 original standing tests + 6 recovered minutes tests + 6 new CAM/GK regression tests |
| Benchmark artefacts | Existing long-run, manager-XI and duration/substitution packages recovered without overwriting results |

Source acquisition and ingestion were run on fresh working copies of the core.
All 15,153 lineup player IDs and all 11,448 average-position IDs map to stable
UUIDs. Both the frozen importer and the isolated CAM importer ingest all 380
matches. Do not use `--replace-source` on historical core or frozen benchmarks.

## Implemented changes, kept separate

1. `eec59a8`: unchanged checkpoint import, preserving its original manifest.
2. `11ede80`: central AM/AMC normalizes to CAM; importer emits CAM; q/H taxonomy
   contains CAM. RAM/LAM remain distinct half-space roles. CM/RW/LW/ST do not
   automatically become CAM. This is an explicit-role correction, not a new
   inference model.
3. `a64eab0`: independently repair missing starting-goalkeeper assignments.
   The original importer otherwise left all 760 starter GK roles NULL. This is
   not part of the isolated CAM comparison and is not promoted on OOS evidence.

`3-4-2-1` retains RAM/LAM when the structure supports two half-space players;
it does not force either to CAM. The importer does not yet combine source
lineup-slot evidence and player role history with coordinates. Geometry fallback
and missing-coordinate uncertainty still need explicit confidence/provenance.

## Actual historical CAM audit

Recovered slot-role artefact: 8,360 starter rows, 20 teams, 38 GWs, 380 fixtures,
474 players; 436 AM starts become CAM (74 players, 19 teams).

The original geometric importer instead identifies 436 CAM starts across 111
players and 19 teams. Its assignments differ from the slot-based artefact for
1,052 outfield starter rows. Four starting players lack coordinates. This
disagreement requires inspection before correcting CM/ST/RW/LW to CAM: those
changes were not guessed. Coverage and change CSVs are in `analysis/results`.

For isolated AM -> CAM, full historical q/H equivalence passes after canonical
renaming: 216,717 player-role states, 11,277 capacities and 38,313 candidates.
The transport regression check also confirms identical start probabilities
under the same role-label permutation. This is feature-equivalence validation,
not an OOS forecast comparison and not evidence of improved accuracy.

## Reproduced existing v2 benchmark

Training: 2023/24 + 2024/25; 2025/26 holdout. Existing fixed half-lives 3/10/3,
same exact-11 constraint and frozen duration parameters; no new tuning.

| Evaluation | N | Brier | Log-loss | xMins MAE | xMins RMSE |
| --- | ---: | ---: | ---: | ---: | ---: |
| GW6–38, reproduced | 26,159 | 0.0774292962 | 0.2595283196 | 11.94116038 | 21.75226256 |
| GW12–38, reproduced | 21,684 | 0.0786022575 | 0.2625060491 | 12.10237966 | 22.07337809 |
| GW22–38, reproduced | 13,987 | 0.0771480448 | 0.2577160094 | 11.95864197 | 21.92247859 |
| GW22–38, saved role result only | 13,987 | 0.0764613817 | 0.2509139917 | 11.64071527 | 21.83175925 |

Baseline matches the saved artefact to floating-point tolerance. Original code
uses GW-based historical filtering; strict actual-deadline/observed_at review is
still required before certifying absence of leakage, especially postponed games.
Per-team/GW/position/starter/bench and posthoc actual-role diagnostics and
calibration bins were generated. Actual-role slices condition on realised
starter roles and therefore are diagnostic, not role-cohort calibration estimates.

The 27-GW scope belongs to GW12–38, not GW22–38 (17 GWs). The claimed 27/27,
25/27 and 19/20 comparisons are not independently reproduced here.

## Remaining benchmark blocker

The reported role benchmark is a separate role-augmented logistic model, not
the standing importer's constrained q/H pipeline. Recovered
`benchmark_manager_xi_augmented.py` explicitly reads
`role_augmented_holdout_predictions.csv`, including `role_fit_fast`,
`role_h_fast`, `role_qmax_fast`, `role_evidence_fast` and slow counterparts.
That predictions/features file and the original script generating it were not
found in the recovered packages. It would be dishonest to invent that model
and call the result a reproduction. Saved role metrics exist and match the
handoff, but the role result has not been rerun.

The standing model's score/importance defaults and the role-augmented benchmark
must not be conflated. No CAM-improved OOS score, team/GW stability claim, new
role-duration shrinkage model or FPL replay is reported.

Existing duration/substitution test artefacts also show why promotion requires
care: their duration trial worsens GW22–38 MAE relative to role-only
(11.66466268 vs 11.64071527) while improving RMSE (21.75110647 vs 21.83175925).
It was preserved as an experiment, not adopted silently.

## Reproducible commands

Run from the repository root. Decompress the frozen database to `/tmp/core.sqlite3`
(or a chosen external working path). No supplied original DB is modified.

```bash
python scripts/run_model_checks.py
python scripts/reproduce_pstart_v2_fixture_minutes.py --db /tmp/core.sqlite3 --out analysis/results/v2-reproduced
python scripts/audit_cam_checkpoint.py --roles analysis/recovered/FPL_MANAGER_XI_ROLE_TEST_2025_26/starter_roles_2025_26.csv --out analysis/results/cam-audit
python scripts/report_minutes_validation.py --predictions analysis/results/v2-reproduced/pstart_v2_fixture_holdout_2025_26.csv --roles analysis/results/cam-audit/starter_roles_cam.csv --out analysis/results/v2-validation
python scripts/compare_cam_role_states.py --legacy analysis/results/legacy-role-state --cam analysis/results/cam-role-state --out analysis/results/historical-cam-equivalence.json
```

To rebuild detailed derived data, copy the frozen DB to a fresh working file,
run `v1_1_init_multicomp_pstart_v2.py --db <working-db>`, then run
`v1_1_ingest_fpl_core_detailed_roles.py --db <working-db> --input-root
data_v1_1/raw/fpl-core-2025-26 --audit-out <new-audit-path>` and
`v1_1_build_role_hierarchy.py --db <working-db> --out-dir <new-feature-dir>`.
For the isolated old/CAM equivalence use the importer/hierarchy versions at
`eec59a8` and `11ede80` respectively; current working code also includes the
separate GK fix.

## Next step and remote checkpoint

Recover the original role-augmented feature builder/predictions file, reproduce
the saved benchmark, reconcile slot-vs-geometry assignments with confidence
flags, and run identical-cutoff OOS comparisons for CAM and GK independently.
Then continue role-dependent minute decomposition and workload/cups/importance.

GitHub branch creation previously returned 403 `Resource not accessible by
integration`. Remote write access has not been enabled in this session; these
commits are local and must be pushed once the connection permits writes.
The old audit commit `1867c0796a59c556efeabab82fcfb99ff04b9804` is preserved.
