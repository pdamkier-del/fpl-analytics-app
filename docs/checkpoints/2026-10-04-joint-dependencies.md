# Original joint simulator restored

Continues verified branch HEAD `8091c857ccc9909637e4884212f534834b9576ac`.
The original Phase 4B frozen-component adapter is restored unchanged.
The Phase 4C simulator is restored with its original transitive modules:
`bps`, `defcon`, `keeper` and `negative_events`.
No existing minutes, roles, workload, transfer or chip-policy code is changed.

`joint-source-recovery-20261004.json` records each source archive's stable
identity, archive SHA256, exact member path and installed file SHA256.
Only selected absent modules/tests were installed; archived `__init__.py`
files and earlier minutes implementations were deliberately not applied.

Validation: `PYTHONPATH=src python -m pytest -q tests`: **100 passed**.
Pytest is declared separately in `requirements-model-tests.txt`.

## Diagnostic protocol, before results

Recover frozen component prediction files and their exact bytes. Use a common
keyed player/fixture cohort, identical team-goal and event inputs, simulator
version and seeded simulation budget for control and v4. No transfer/chip
policy change, model fitting or candidate selection. Preserve the existing
control; record precisely which minute inputs differ. Report missing joins
explicitly rather than filling unavailable components with zero. GW22–38 is
a reused diagnostic, never a fresh holdout or independent OOS claim.

The archived adapter divides fixture event means by expected minutes to
recover on-pitch propensities. Candidate minute changes must not accidentally
change these propensities by retaining fixed event means with a different
denominator. Build the common control input once, then replace only the
candidate minute fields on its simulator inputs.

The original simulator uses `bps_2026_27` on 2025/26 data and approximates
unobserved BPS background. Preserve that scoring in both diagnostic arms to
isolate the minute change. Audit and resolve season-rule/scoring limitations
separately before any full season replay; do not call this exact 2025/26 xP.
