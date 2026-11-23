# Phase5 — original full-pool TS funding feasibility

23 November2026. **Practical feasibility gate FAILED. Deprioritize this unchanged candidate.**

- Exactly12states attempted; all12baselines and12keep-controls finish. Candidate finishes10and times out on states3and4at120seconds. No retries, extra states or budget extension.
- All10completed paired comparisons have **Δ=0**. No observed gain or regression there; full12state mean/median and non-regression are **unknown**, not imputed or complete-case primary estimates.
- Baseline end-to-end16.21–20.77seconds (median18.98). Completed candidate60.26–115.35seconds; two additional120second timeouts. Runtime/coverage gates fail. Full12candidate p90and median paired ratio remain unreported because of missing completed arms; this cannot rescue a failed timeout gate.
- Original preflight30.5341s+v2run1414.8197s=**1445.3538seconds (24.09minutes)** of active run wall time, within3600s. No scenario/roster/horizon reduction.
- Across34completed arms, all204nomination/scalar audits and204six-GW transition/action checks pass. Two timed-out candidate paths remain unverified. No observed model/scorer/accounting discrepancy or illegal decision in completed paths; no blanket correctness claim.

## All twelve outcomes

Weighted forecast utility after original costs/buffer, not real FPLpoints. `NA` means no completed candidate plan. Timed-out runtimes include process termination overhead around120s.

| State | FT / bank (£0.1m) | Baseline U | Candidate U | Δ | Keep U | Baseline / candidate seconds |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 01 | 1 / 0 | 110.012455 | 110.012455 | 0.000000 | 90.817826 | 16.21 / 101.47 |
| 02 | 1 / 0 | 113.521106 | 113.521106 | 0.000000 | 96.824821 | 19.25 / 79.33 |
| 03 | 1 / 0 | 112.116834 | NA (timeout) | NA | 96.919738 | 20.08 / 120.01 |
| 04 | 1 / 10 | 106.944006 | NA (timeout) | NA | 85.366974 | 18.81 / 120.07 |
| 05 | 1 / 10 | 109.956369 | 109.956369 | 0.000000 | 90.849703 | 18.81 / 108.53 |
| 06 | 1 / 10 | 111.430830 | 111.430830 | 0.000000 | 89.080960 | 18.65 / 112.46 |
| 07 | 2 / 0 | 107.575854 | 107.575854 | 0.000000 | 78.397022 | 19.15 / 71.12 |
| 08 | 2 / 0 | 118.396023 | 118.396023 | 0.000000 | 96.669329 | 20.77 / 115.35 |
| 09 | 2 / 0 | 114.114444 | 114.114444 | 0.000000 | 88.191277 | 17.37 / 60.26 |
| 10 | 2 / 10 | 115.827654 | 115.827654 | 0.000000 | 94.975772 | 20.00 / 87.14 |
| 11 | 2 / 10 | 119.773162 | 119.773162 | 0.000000 | 98.062538 | 16.50 / 65.05 |
| 12 | 2 / 10 | 122.132920 | 122.132920 | 0.000000 | 102.785892 | 20.72 / 100.31 |

Raw first-run paths, objectives, costs, timings/RSS and failure statuses are in v2-attempt/result.json and per-arm files. cases.csv and strata.json preserve all four fixed strata. Paired coverage by stratum is2/3,2/3,3/3,3/3; every observed delta is0. The incomplete strata are not replaced, pooled as independent GWs or relabelled successful.

## Acceptance and decision

1. **All12pairs/control/audits:** FAIL, two missing candidate plans.
2. **MeanΔ≥.25;≥3improving states in≥2strata:** not demonstrated.0/10completed pairs improve; full12mean unknown.
3. **No state worsens:**0observed regressions, but full12non-regression unverified. No pass claim.
4. **Runtime p90≤30s, median ratio≤2, all arms≤120s:** FAIL, completed candidate times all exceed30s and two arms time out. Missing results are not given finite successful runtimes/utility.

**Recommendation:** stop investing in this unchanged funding implementation as the next production candidate. Its small-domain synthetic improvements do not translate into a demonstrated gain on this fixed real-pool stress set, while runtime is already impractical under the registered requirements. This is not proof that funding transfers never help, or that TSv3is optimal: ten equal results and two unknowns cannot establish either. Timing isolates the candidate package under fixed scorer/config, but no profiler separates pair enumeration from changed beam pressure. Do not tune on these12seen states or relax the gates.

Prioritize the already-frozen PR54MM/PMfuture observation and verified capture. Any later funding/search revision needs a separate concrete mechanism, new protocol and untouched states; real-manager/realized-value evidence also needs verified private capture. No new experiment or optimization is launched here.

## Tests and verification

-5new unrelated identity/roundoff/scorer contract tests pass. Original source/scorer/config loaded; no evaluation-state generation by tests.
-Existing broad offline research suite:89pass,2fail. Failures are **snapshot counts**: research/tests/test_registry.py expects65entries (now66); research/stage0/tests/test_stage0.py expects11reconciliations (already13atPR56base). Current canonical registry validates66entries and original protected8GW/80match protocol. The latter failure predates this task; this task adds no reconciliation events before final result recording.
-These assertions and PR54's frozen manifest-covered test are preserved and the failures disclosed, not silently weakened. A separately versioned registry-infrastructure update is required before integrating this expanded research stack's checks into main. No live workflow was changed here.
-All65prior protocol bytes, old events prefix, original PR56protocol, PR50candidate, frozen161source and PR54current implementation manifest match their recorded hashes. No model/app/substitution changes, prospective result use or deployment.

These are94passing tests plus2known metadata-snapshot failures, not a claim that the complete inherited suite is green. Tests verify declared contracts; they do not validate future predictive accuracy.


## Frozen design and actual input

PR56protocol is unchanged. Original revisionf54f651e…, canonical forecast4d1a2e39… and raw8f80f078… recover through pinned C2helpers and full archive validation. Original674players,4044player-GWrows, sixGW12–17and400shared draws are retained. Native participation identifies353eligible owned players; the planner's incoming pool retains all674. No new payoffs, altered arrays, live prices, outcomes or private managerstates.

Registration/code v1commit35e06b73 preceded input application. Original adapter's strict exact-[0,1] native probability check rejected308/4044rows,100in originGW, with maximum negative roundoff2.4424906541753444e-15. Existing frozen B-chain validator itself passed. This was an input-guard false rejection, **not evidence that the original forecast was untranslatable**. No states or numerical arms were generated in v1. Preserve first-attempt/result.json and input-roundoff-diagnosis.json.

Separately registered v2commit45a89aa1 admits guard tolerance1e-12without clipping/replacing any stored value or changing p>=.20eligibility. The original object passes through unchanged. Candidate, scorer, protocol, test-state seeds, utility/runtime thresholds and budget remain identical. First30.53412413299884seconds count against the same3600second budget. This occurred before state generation or efficacy inspection; not a numerical retry or candidate adjustment.

All12states were generated as prescribed, committed together ine20c1046before any arm. state-validation.json records costs/resource strata/seed/hash/legality; generator was not rerun. Each arm fresh process, same original inputs, one numerical thread, alternating A/Border; independent keep and scalar nomination/state/utility checks. Full input is not exhaustive full-pool search: original target/beam pruning remains frozen. No exact optimum or realized-point claim.

## Reproducibility and limitations

See ts_realpool/README.md, immutable implementation manifests, registered commands, raw result.json and per-arm files. A future reproduction uses pre-run snapshot45a89aa1with a fresh output/cache, not reset/overwritten first-run evidence. States are now seen. Source/model/configuration/protocol hashes are retained and checked. Public original inputs remain in original Release; redundant recovered files in/tmpare not committed. All published states are synthetic, never private manager records.

Single shared host AMD EPYC9V74, one numerical thread and one arm at a time; not dedicated-core benchmarking. Completed process RSS high-water range242672–242928KiB (about237.2MiB); timeout worker high-water not retained. Conservative wall upper bound from first implementation commit to final run output is1540.0s, also below3600s, including the intervening input-guard correction. Peak RSS is Linuxprocess high-water including process launch/imports and may inherit launcher high-water; it is not an isolated algorithm-memory delta. Timeouts have no completed worker self-report. Do not infer equal memory use from equal peak values. No new football observations or PR54prospective results are used.
