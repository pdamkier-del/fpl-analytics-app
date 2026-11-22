Implements only Monte Carlo precision, compact browser transport, FWD-assist calibration and integration tests. Injury-return/P(90) work belongs to the separate MM Codex and is explicitly excluded.

Shared-interface contract: [docs/tasks/2026-11-01-B-shared-interface.md](https://github.com/pdamkier-del/fpl-analytics-app/blob/improve-b-stability-calibration-20261101/docs/tasks/2026-11-01-B-shared-interface.md).

- Current B forecasts select 2,000 draws; validation/close mode selects 10,000 within an explicit fixture/draw budget. Fixture-identity seeds and unchanged scoring preserve paired/nested comparisons.
- Complete aligned scenarios remain in canonical forecast.json for the original private TS backend. The browser receives a derived summary with a separate byte hash and the canonical forecast identity.
- Fitted assist candidate is being tested on fixed later periods; no activation unless its paired calibration/xP gates pass.
- No changes to MM probabilities, duration model, role kernel, physical invariants, locked PM/TS sources, original benchmarks, production app or immutable prospective forecast log.

Coordination: merge/retest shared run_joint_gk_preview.py changes via PRs; do not replace the other MM branch. A combined source must repeat integration and calibration gates. This PR will record final CI, diagnostics and preview evidence before it is marked ready.

Assist gate completed: accepted on both fixed diagnostic windows; pooled paired fixture-bootstrap FWD-assist Brier delta 95% interval [-0.000679, -0.0000456]. FWD xP bias improves, but FWD xP-MAE worsens slightly; overall MAE deterioration stays below the preregistered limits. No independent accuracy claim. The same-source current control asserts unchanged MM marginals. Four 10k-draw historical controls × two seeds confirm exact nested 2k prefixes and unchanged minute/goal draws. 1,129 local Python tests pass. Fresh six-GW/TS/publication integration is being rerun at 817737be after fixing the versioned policy path in CI.
