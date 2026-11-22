# C1 Stage 0 — decision report

**22 November 2026 · branch-only historical reconciliation · no model optimization or app changes.**

The original register was incomplete. The reconciled public inventory assigns **184 result directories to 54 coverage families**, preserves all original 25 protocols/events, and adds **38 missing historical registrations** (`LEGACY-016`–`053`). Families collect related arms and repeated artifacts; neither count is a count of independent holdouts. Read the [historical matrix](HISTORICAL_MATRIX.md), [directory matrix](directory-matrix.csv) and [ranked gap/novelty matrix](GAP_MATRIX.md).

## Decisions that matter

- **Do not rediscover TS exact enumeration:** the November audit already enumerated six one-GW ≤2-transfer cases. Archived gaps are zero, with a separate maximum nomination gain .18xP. Per-transfer scoring still uses a heuristic nomination; the one-GW buffer1.5 differs from the frozen current buffer1.0. TSv4 MILP/FT/enabler tests also exist. The remaining proposed experiment is an **independent current-scorer finite-domain reference**, not “first exact TS test” or season improvement.
- **Do not repeat MM research as new:** survival/score hazards, role/duration/return ablations, workload, formation and minute laws are existing studies. B's reported minute-MAE gain .1130 on 39,264 reused rows is method-development evidence, not independent confirmation. The later return/P90 candidate has only limited control evidence and a pending full analytic run in PR 30 prose; its completeness is not inferred.
- **Reuse the secondary PM study before any CS/BPS candidate:**341 old fixtures already have component calibration, rule-derived CS checks, all-fixture actual-BPS tie checks and 849 DC boundary checks. The keeper-stint reserve correction is an existing opt-in semantics repair. Missing direct CS/timing/penalty split labels and inherited fit clocks limit empirical selection. Position-specific GK BPS/bonus signals are already known; no global CS/BPS multiplier is justified.
- **Dynamic team goals were also tried:** preserve the prior adaptive/opponent-adjusted branch and successful CI metadata. Numerical results could not be retrieved: artifact/log downloads returned Forbidden. The input URL is mutable and not checksum-pinned in the script. No rerun or numeric conclusion is substituted.
- **Protected prospective trial stays unchanged:** fresh read-only observation still shows0 completed GW/0 matches, GW 11pending in the21 Nov ledger. All original 8 new GW/80 matches remain to be counted; the older20 matches never count toward that gate. This does not assert there have been no real matches since the ledger update.

## What was actually verified

`verification.json` records all 2,471 original PR 41 file SHA256 matches against`fd3907f4`, existence of 236 original test-source paths,58 public branch refs at48 unique heads,3,169 distinct path/blob versions,225 hashed primary result/protocol artifacts and 21 selected original source copies. Exact source bytes and original protocol/event prefix are checked. TS summary identities, assist-gate differences and the keeper-reserve analytic counterexample were recomputed from existing evidence. No simulation, fit, optimizer or model suite was run.

**Verification is bounded.** It does not independently reproduce every old scientific result, prove historical publication clocks, or rerun old CI. Old effects/intervals retain their original selection, dependence and rule-year caveats. Matrix cells without recorded metrics/intervals/cutoffs remain NOT_AVAILABLE. One manager-specific branch and all private-manager payloads are excluded; this is not proof no private study ever occurred. Successful old CI metadata alone is not efficacy evidence. The independent scientific review checkbox is deliberately **pending PR reviewer confirmation**.

## Concrete next experiment and cost

After that review, proceed only with the remaining `EXP-TS-SEARCH-001` measurement: inspect the old enumerator, preserve frozen TS code/scorer, register an independently checkable harness, then use the existing30 deterministic +12 restricted-DNP cases, pool≤17, transfers≤2, scenarios≤8 and initial120-second execution limit. Report legality/scoring disagreements and all utility gaps. Estimated harness work1–2 development days; no measured execution time is claimed. No new match outcomes or model parameters are required.

In parallel, the valid low-compute PM task is a consolidated event dictionary/coverage contract reusing old mappings (rough1–2 days), **not another component audit or parameter fit**. Independent MM efficacy needs original future captures and its separate12-GW/120-match gate. Stateful TS and commercial comparisons remain data/privacy/rights gated. [GAP_MATRIX.md](GAP_MATRIX.md) maps every proposed protocol to its precise prior overlap and missing prerequisite.

## Reproduce the reconciliation

```sh
python research/tools/registry.py validate
python research/tools/registry.py status
python research/tools/registry.py next
python research/stage0/code/verify_sources.py
python research/stage0/code/collect_sources.py --source-git /path/to/full/repo
python research/stage0/code/verify_sources.py --source-git /path/to/full/repo
python research/stage0/code/build_matrices.py
python -m pytest research/tests research/stage0/tests -q
```

The full Git checks need the pinned source objects named in`source-refs.json`, plus`fd3907f4` and the original audit test refs. No command above acquires new match data, fits a model, calls the optimizer or changes production. Refreshing live GitHub metadata is a new dated observation, never an overwrite of these receipts. The matrix renderer writes only its derived matrix artifacts; the verifier is read-only unless an explicit output path is supplied.

Actual deterministic validation: **20 tests passed in 0.83 seconds**; registry validates 63 entries. Initial metadata-test failures and corrections are retained in`test-receipt.json`; they were bookkeeping defects, not new model results. Full pinned-tree/hash and collector checks also passed. Old model suites were not executed.
