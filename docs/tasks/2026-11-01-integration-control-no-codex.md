# Integration control — no-Codex period, 1–4 November 2026

This is a **review-only control document**. No production, B preview or model sources changed. The existing app must stay usable. Evidence reviewed at PR heads on Nov 1.

## Actual PR topology

| PR | Head | Base | Decision now |
|---|---|---|---|
| #22 | experiment-goalkeeper-coverage-20261018 | integration-mm-live-20261017 | Working B preview / reference; nested base, not direct main merge |
| #29 | audit-systematic-precision-20261101 | main | Frozen evaluation reference; do not confuse reused samples with independent validation |
| #30 | improve-b-return-p90-20261101 | audit-systematic-precision-20261101 | **HOLD**: 4-match xP check; full 341-match before/after still incomplete in PR description; tradeoffs |
| #31 | improve-b-stability-calibration-20261101 | main | **HOLD**: mergeable=false at review, integration CI/fresh six-GW still being rerun; assist fit changes xP-MAE slightly adversely |
| #32 | test-pm-secondary-calibration-20261101 | audit-pm-secondary-components-20261101 | **RESEARCH-ONLY**: keeper-reserve adapter opt-in, dynamically recompiles and monkey-patches simulator |

## Order and explicit gates

1. **Freeze baselines:** capture head SHAs and checksums for #22/#29/#30/#31/#32 and the deployed B-preview. Do not merge #29 or #32 into main merely to acquire diagnostic files.
2. **Resolve #31's base conflict without blindly replacing files:** locate its main-base versus B-integration ancestry and bring forward *only* approved feature changes: deterministic 2k/10k current draw modes, compact *browser-only* payload, canonical TS scenario preservation. Preserve old `run(... draws=400)` reference and predeadline seal. Confirm throughput, memory, URL and payload; 10k should not indiscriminately run for every fixture.
3. **FWD assist gate after merged MM:** #31's paired bootstrap FWD-assist Brier CI excludes zero on reused history, but FWD xP-MAE **worsens slightly**; do not state unequivocal overall xP improvement. Confirm same-source fixed draw comparisons. Rerun after #30 if MM activated.
4. **MM #30 must earn promotion:** per-group minute bias/MAE, P(start), P(60), P(90), final xP and paired uncertainty on full 341 historical fixtures; preserve physical/legal XI/keeper constraints. Do not promote from four matches. If no documented gain, keep old B MM.
5. **Keeper save-reserve #32:** analytical 45/45 situation changes predicted 1.2/.8 to target 1/1, but current repair is `experimental_keeper_save_reserve` using AST-compilation and context-scoped monkey-patching of `b_event_simulator.simulate_match`. It is not a production-ready concurrent implementation; keep opt-in, revisit clean extension point *if and only if* a real production path needs it. No new generalized keeper-rate/DC/BPS parameters.
6. **Re-run full chain:** one actual fixture → one GW → six GW MM→PM→private TS; paired xP and decisions (captain, VC, XI, transfers), 1,139+ relevant regressions (non-additive suites), scenario alignment and no unauthorized production-file diffs.
7. **Prospective sealed evaluation:** make GW10–15 checkpoint at true predeadline cutoff; no fixture outcome joins in forecast generation. Keep promotion human-reviewed until held-out future labels are available.
8. **Model Explorer later:** read-only model version manifest, component attribution with common matched draws and interactions; explicitly label Monte Carlo stability as numerical precision rather than better football forecasts.

## Current blockers that should appear in any integration PR

- #31 was reported `mergeable=false` against main at review; no attempt made here to merge or fix because combined ancestry needs inspection and another agent may still be writing.
- #30's reported historical completeness was not proven when PR metadata was last read.
- #32 CS labels are rules-derived, not independently observed; MID/FWD DC and GK BPS deviations are diagnosis only.
- Source provenance for inherited fitted PM coefficients is incomplete; reused audit cohort cannot prove independent out-of-time predictive improvement.

**Acceptance:** one reviewed integration PR on a dedicated branch, with exact model and data hashes, CI green, browser mobile/desktop checked, and no production activation before user approval. Prefer no merge to a false sense of completed integration.
