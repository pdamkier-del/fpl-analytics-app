# Current C1 handoff — Stage 0, 22 November 2026

**Separate research PR:** [#47](https://github.com/pdamkier-del/fpl-analytics-app/pull/47), based on PR #45. No merge/deploy.

**Scope delivered:** historical reconciliation only; no model optimization, simulation, TS search, app edit or deployment. Original 25 protocols and original event prefix unchanged;38missing historical records appended (63 total). Stage0 independent scientific review remains pending; do not tick it merely because tests pass.

1. Read `C1_README.md`, `stage0/REPORT.md`, `stage0/HISTORICAL_MATRIX.md`, `stage0/GAP_MATRIX.md` and the separate Stage0 PR review.
2. Run `python research/tools/registry.py validate`, `status`, `next`, `python research/stage0/code/verify_sources.py` and the research tests. For full provenance, follow the `--source-git` commands in the report.
3. Check live PR metadata. On22 Nov: #41/#42/#45 open and stacked; #43 and #44 open draft. None is assumed merged. This branch is based on #45 at`329f67bcb691390ab744aa5249a012e6ab4f8da3` and changes only `research/`.
4. Review novelty and evidence gaps first.184 result directories map to 54 coverage families, not54independent experiments. All 2,471 old hashes match;236 test-source paths exist;225 primary artifacts and 21 selected source copies retained. No full model suite or scientific rerun occurred.

## Next valid recommendation after review

Keep `EXP-TS-SEARCH-001` unchanged, but inspect LEGACY-040/044/045 before implementing it. Existing `precision_audit/decisions.py` enumerates all ≤2-transfer squads in six one-GW historical cases, with heuristic nominations per squad (buffer1.5), and separately exact nominations for the unchanged squad. Existing TSv4 MILP tests cover FT saving and negative-leg budget enablers; its one-GW smoke is not a full current shared-PM oracle.

The residual task is independent exact comparison under the frozen current scorer/config and registered domain, including the six-GW utility and joint transfer/nomination boundary.30 deterministic +12 restricted-DNP cases, pool≤17, ≤2 transfers, ≤8scenarios, initial120 seconds remain the original bounds. Register the actual immutable harness/command before running. Do not run or optimize it in a continuation that only authorizes reconciliation. If independent review finds no residual novelty or feasible harness within bounds, record blocked/overlap and choose PM definitions; do not change the protocol silently.

## Preserve these observations

- New records`LEGACY-016`–`053` import old findings; their completed registry state means reconciled historical record, not independent efficacy or that all queued runs completed. Classifications in the evidence distinguish rejected exact configurations, reused/exploratory, inconclusive and blocked work.
- PR 29 already has M/S/G oracles and MC-stability work. PR 30 return/P90 full analytic completion is not established by the committed four-fixture controls/PR prose. PR 31's accepted assist gate uses reused periods; no independent gain or production activation is inferred.
- PR 32 already contains 341 fixture CS/save/DC/BPS diagnostics,849DC boundary checks and 341actual-BPS tie checks; keeper-stint reserve repair is opt-in only. Reuse its definitions before EXP-PM-DEFS-001; no new global CS/BPS calibration is justified.
- Team-xG branch`17cab2b4` and Actions run41481313449 exist. Artifact13160057601 digest is retained, but artifact/log body download failed Forbidden. Numerical findings remain unverified, mutable source input not pinned; do not rerun under the guise of verification or say dynamics were never tried.
- Fresh read-only substitution ledger observation22 Nov still shows21 Nov update, GW 11pending,0completeGW/0 matches. Original 8newGW/80 matches still missing from counted evaluation; old 20 do not count. Candidate/model/kernel/protocol/workflows remain untouched. No capture/scoring action was triggered.
- Private manager-specific branch/payloads excluded. No inference that the repository has never had private studies. No private data to Git/Pages/CI. Public source references and aggregate model-constructed TS historical cases only.
- C2 owns private-capture/integration work. Known bench-label gate in draft PR 43 and unverified durable private storage are not resolved here; PR 44 must be reviewed for overlap. No C2 branch edited.

## End of next session

Keep original protocols/results and initial decisions; append evidence/state/implementation events with actual checksums. The new `evidence_reconciled` event preserves state and implementation and verifies local immutable evidence. Update status and handoff explicitly. Independent scientific review is external PR review, not a self-check. No automatic promotion.

---

# Historical handoff from PR45 base — retained for chronology

The following was the earlier handoff before the Stage0 reconciliation above; its incomplete research coverage is superseded by the dated evidence above, not silently erased.

# Exact handoff for the next Codex session

## Start

1. Read root `MASTER_PLAN.md` and `research/MASTER_PLAN.md`.
2. Run `python research/tools/registry.py validate`, `status`, `next`.
3. Check current user scope and source receipts. The recorded state is as of22November2026; refresh read-only job status before using a later outcome. Never rewrite the stored receipt to look current.

## Highest-priority valid new task

`EXP-TS-SEARCH-001` is scientifically/data ready; its exact-reference harness is **not yet implemented**. Do not claim a performance result yet. Read its JSON and METHODOLOGY§5, then create an isolated research branch and implement a bounded exact harness using the unchanged original scorer/config from `161b67b6fb8786a38e78c245b92a03ad841575d8`.

Baseline sources/recipes already exist in the Git history and audit source copies; do not copy new parameters into production. Use deterministic all-play finite-pool legality/search witnesses, then a separately declared reduced nomination domain with DNP/captain fallback. Keep the domain and2-minute initial runtime cap; no season simulation. Hand-derived examples must agree with the exact reference. Record the implementation command/hash before execution. Report all heuristic gaps; a miss is not automatically proof of a scoring bug or of worse real-season decisions.

## Work that must not be lost

- PR41 `d28bfe3c`: comprehensive audit and original evidence.
- PR42 `0a08c3d7`: deterministic audit fix, PM decomposition and standalone private logger.
- Draft PR43 `ddd47e3e`: operational integration WIP. Ten report tests, ten capture tests, two HTTP tests and14original logger tests passed individually. The real frozen-worker capture regression FAILED because of bench labels (`GK bench`/`Bench 1…3` versus `BGK`/`B1…3`). That failed gate is intentionally preserved; do not call the draft release-ready. End-to-end public recovery, DGW/blank adversarial coverage, persistent private storage and verified-execution ingestion remain incomplete. This planning branch includes none of its service/pipeline changes.
- The original substitutions trial is unchanged; local and remote fit/kernel hashes matched in PR42. Latest recorded observation: GW11pending,0completeGWs/0matches. It needs its original8newGWs/80matches; its old20matches do not count. It can use eligible GW11 under its older registration; new MM/PM studies cannot reclassify already begun GW11 as a fresh registered holdout.

## Other valid paths

MM prospective measurement can start collection only after original-vintage pipeline gates; earliest new originGW12. PM target/schema work is ready and must build on, not repeat, the existing decomposition. Commercial benchmarking is blocked by unavailable verified rights/data. Stateful TS gain is blocked by missing complete private observations and horizons. No additional manager data should be uploaded or published to unblock the plan.

## What to update after future work

Append an implementation/state/result event with immutable evidence and the actual outcome, regenerate STATUS explicitly, append a decision-log entry and update this handoff with a dated addition. Never silently edit old protocols/results. If the next user authorizes a different scope, preserve this history and register the new question rather than erasing it.

## Additional open work observed before this plan was finalized

PR44, “Introduce a fail-closed model/TS interface boundary for the live FPL app”, was found open in a concurrent workstream. It has not been reviewed or integrated by this planning task. Read its current diff/status before implementing overlapping interface/capture work in PR43. Its existence is not evidence that the known original-worker capture gate or production certification is resolved. Do not duplicate or overwrite that work.
