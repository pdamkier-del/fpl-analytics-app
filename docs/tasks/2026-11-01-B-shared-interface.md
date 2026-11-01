# Ownership and shared interfaces – 1 November 2026

User delegated injury return/P(90) to a separate Codex after this task began.
This branch stops and removes its unactivated MM candidates. It owns only
Monte Carlo precision, browser summary transport, fitted FWD-assist allocation,
and integration/release tests. No changes to MM p/q/s/c, role mixture,
PhysicalKernel, physical/FPL clocks, goalkeeper coverage or substitution rules.

Coordinate through this branch's PR; do not cherry-pick/overwrite another agent's
branch or re-fit its MM model. Numerical reference: `161b67b6` (integration) and
`c18cfa4b` (audit).

Shared `scripts/run_joint_gk_preview.py` interfaces:

- `run(..., draws=400, offsets=None)` remains a historical reference. Current
  `current(..., precision_mode='normal', draws=None)` explicitly selects 2,000;
  validation/close mode selects 10,000. The stable fixture seed is independent of
  batch ordering; all full-horizon/subset checks must use the same offsets/N.
- A proposed optional `assist_policy=None` hook only changes `assist_weight`.
  It consumes current kernel analytical minutes and pregame slow tactical role
  weights from the PM frame. It must not change minute fields or reconstruct
  role probabilities. Any activation is content-linked to assist gate results.
- The other MM PR may update minute inputs/kernel before this assist hook.
  A combined source must repeat MM→PM→TS tests and the assist nonregression gate;
  a calibration validated on old MM is not automatically evidence for new MM.
- `scripts/b_simulation_precision.py` derives `browser-forecast.json`; the full
  sealed `forecast.json` stays canonical for the existing private TS backend.
  Browser request IDs use that canonical seal. No TS rules/backend deployment
  change is required. Derived transport has a separate byte hash, not a new
  pretend model seal. No raw arrays are removed from server inputs.
- Production's 88 published files, locked PM/TS sources, all prior benchmark
  files and the prospective audit forecast log remain unchanged.

The MM candidate code and its partial numerical scratch results were not
activated, committed or published. They are outside this branch's deliverable.
