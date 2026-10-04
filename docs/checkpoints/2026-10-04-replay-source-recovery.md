# Existing replay engine recovered

Continues `0fc1432a1c9310ad5a48625f59f5fa3f4e0925fc` on the audit branch.
Recovered exact archived Phase 5Y bytes into the previously absent `fpl_xpts`
namespace: `season_replay.py`, `optimize.py`, and nine replay assertion tests.
Archive identity, SHA256 and per-member checksums are recorded in
`replay-source-recovery-20261004.json`. No reconstructed replacement engine.

All **70 tests pass**, including sale-price rounding, vice-captain/autosubs,
three-player club limit, simultaneous transfer bundles, five free transfers,
chip timing, and the existing two-point uncertainty buffer on hit decisions.
These are contract tests, not proof of full-season points or correct scoring
rules for every season. The archived chip policy requires a season-specific
rules audit before new simulations.

The Phase 4B archive contains the original frozen-component adapter and joint
simulator; Phase 4C contains a subsequent simulator version. They were located
and downloaded for inspection, but are not installed in the active namespace:
their imports also need `bps`, `defcon`, `keeper`, and `negative_events`.
Phase 5E was located for team-goal/control recovery. Archive candidates and
identities are preserved in the recovery record for the next continuation.

Next: recover and verify the simulator's transitive components and original
frozen forecasts; retain each version's provenance, check scoring rules and
event-rate/minutes contracts, then attach v4 for a paired diagnostic against
the unchanged control. GW22–38 cannot become a fresh test by rerunning it.
Cup coverage, as-of competition state and independent validation still remain.
No app activation, xP improvement claim or full-season simulation at this step.
