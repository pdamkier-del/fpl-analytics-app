# Verified paired deadline-input diagnostic

Continues d450116d2779e533ab2c6d84431d86e23b8d3f38. No restart, fitting or policy changes.

All 144 complete fixtures / 11,794 player-fixture rows ran successfully through the original frozen adapter and simulator. Both arms share the newly frozen common deadline components, team means, keeper state, scoring, fixture roster and seeds/budget; only the original control versus selected v4 minute fields differ. The 26 blocked fixtures are excluded identically. Predictions were saved before evaluation targets were read. This diagnostic uses 80 draws per arm per fixture, seed base 26092501; divergent branches mean seeds are not event-aligned common random numbers.

Bonus-neutral MAE: control 0.8570565542, v4 0.8317438952 (difference -0.0253126590). RMSE: control 1.5915685497, v4 1.5857671288 (difference -0.0058014210). This is technical sensitivity on reused GW22–38, not independent validation or a precise ranking. Do not compare these values directly with the older 137-fixture run: both common inputs and cohort changed. Full-point metrics retain the inherited 2026/27 BPS-on-2025/26 limitation and are secondary diagnostics only.

117 tests pass via `PYTHONPATH=src python -m pytest -q tests`. Frozen prediction checksums, row partition, recomputed primary metrics, original code checksums and all three transfer/chip policy hashes pass. 12,896 common input checks pass. Results and verification are in `analysis/results/deadline-joint-paired-diagnostic-v1`.

The simulator is technically ready for controlled paired replay on this bounded complete-fixture cohort, and that run is now complete. Full-period expansion remains blocked by 32 roster rows across 26 fixtures lacking authoritative predeadline team/position evidence. Recover evidence rather than imputing eligibility from future data or silently dropping players. History uses explicit kickoff+3h guards, not verified publication timestamps. See [season rules audit](2026-10-04-season-rules-audit.md) before any full-season decision replay; scoring alignment and chip rules remain outstanding independently of this successful technical run.
