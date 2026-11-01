# Exact single-pass preview replay

Baseline source commit: `093b7d8`, before the preview stopped replaying all matches a second time. The observer records only immutable scalar values from each already-computed match. No randomness, event calculation, input inference or scoring formula is added to the observer.

`replay-fingerprints.json` records identical before/after hashes for 100 fixed real historical fixture inputs spanning two seasons: individual result/event/BPS fields and generator states, all aggregate outputs, every preview probability, penalty split and all raw weekly-input scenario values. Both serialized replay receipts match byte for byte. This is an implementation-equivalence check, not a new forecasting-quality experiment.

Reproduce with `analysis/check_scoring_refactor_parity.py --preview`, under `scripts/locked_numerical_runtime.py`, using the same prepared historical tasks as the earlier scoring cleanup. Its default mode remains compatible with the original scoring-cleanup fingerprints.

The existing preview call-count test now asserts n sampled matches rather than 2n while retaining independent output/probability checks. A further test checks aggregate and raw-scenario equality under the shared role-lineup sampler. See `tests.json` for full and subsequent targeted test runs. The NP source guard pins the revised simulator, preview exporter and parity receipt; no source-integrity guard was removed. Production and the published B are not redeployed by this change. The known physical-substitution-process limitation remains unresolved.
