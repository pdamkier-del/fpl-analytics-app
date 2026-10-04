# Recover original component parameters before resolving cold starts

Continues `4404b714d8e913a96720513eab31e3b0f4e61717`. Restored the original
Phase 3C attack allocation module and its four tests, plus the archived attack,
DC and discipline fit JSON files. No optimization, fitting or forecast changes.
Archive/member/installed SHA256 and persistent source IDs are recorded in
`analysis/results/joint-component-recovery-v1/manifest.json`.

The 46 absent rows have no earlier 2025/26 Core observation before the frozen
v4 cutoff. The original component experiments deliberately require nonempty
minutes history, so these rows cannot be reproduced merely by rerunning the
original experiment. The recovered shrinkage parameters exist; first-entry
eligibility and the forecasting contract still need a separate audit.

Transfer/chip strategy, original adapter, simulator and both prior diagnostic
arms are unchanged. GW22–38 remains reused diagnostic, not a new holdout.

Validation: `PYTHONPATH=src python -m pytest -q tests` — 107 tests pass.
Next: publish a per-row cold-start/registration audit with explicit evidence
and recovery requirements, without filling missing forecasts with zero.
