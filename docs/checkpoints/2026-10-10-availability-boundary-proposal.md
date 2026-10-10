# Live availability boundary — tested candidate, not activated

Date: 2026-10-10. Continues [the live integration checkpoint](2026-10-10-live-final-integration-checkpoint.md).

## Decision needed before release

The **frozen** `run_mm_unified_official_roles.compose` is unchanged:
`xmins=p_start*start_minutes+(1-p_start)*q_sub*sub_minutes`.
The historical `run_mm_v2_team_news_availability_experiment.py` runner
caps `p_start` at zero for OUT/SUSPENDED but leaves `q_sub` untouched.
Thus frozen raw forecasts may include positive cameo minutes for a certified
unavailable player, violating `mm_release.validate_mm_release`.

A **separate, opt-in live candidate** is now available at:
`src/fpl_v1_1_model/live_availability_boundary.py`.

It accepts a complete existing MM table, and the **original frozen model**
`p_start, q_sub, sub_minutes` arrays. It first verifies the original raw
`xmins` equals the unchanged `compose` formula. Only for documented
impossibility (OUT/SUSPENDED or cap=0) it sets the *effective release-level*
`q_sub` to zero, invokes the same unchanged `compose`, and keeps:
`mm_raw_xmins`, `mm_raw_q_sub`, `live_effective_q_sub`,
`live_eligibility_minutes_removed` and a versioned rule string.

It **does not** modify any coefficients, weights, trained models,
historical scripts, historical benchmarks or main production release
pipeline. Its predictions would **differ** from the unadjusted frozen
historical model on ineligible-player rows, so it must NOT be described as
strictly identical final mathematics or silently promoted.

It rejects incoherent raw inputs, an OUT/SUSPENDED state with a nonzero
availability cap, a zero-cap player with nonzero P(start), and a mismatch
between the origin GW and the source Team News GW. A GW6 OUT observation
is not applied to GW7–11 by assumption.

## Verified regression evidence

[Candidate test run 38035990860](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38035990860):
**13 passing tests**, covering the candidate, existing original conflict,
existing release validation and the unchanged compose source assertion.
Tests do not constitute live MM/PM/TS/chip integration.

## User decision — approved for live integration

**Approved 2026-10-10.** The user explicitly accepted the isolated hard
availability release-level gate and requested that the user interface display
**"Not available"** for affected players. Use this decision in the remaining
live MM → vFinal → TS → chips integration. No additional approval is required
for this exact documented availability policy.

This authorization does **not** permit changing frozen model coefficients,
replacing actual locked-model forecasts with experimental/FPL estimates,
asserting that the live chain has run, or propagating a next-GW unavailability
observation automatically into later gameweeks.

The isolated adapter should be integrated only after the original MM inference
has produced model-derived p/q/duration and passes all release tests. A verified
final release remains blocked until then.

The shared UI helper `app/availability-ui.js` labels official hard statuses
(`i`, `s`, `u`) **Not available** for the next GW, and does not mark
doubtful (`d`) as unavailable. The UI label never constitutes a substitute
for enforcing zero minutes in the real MM release pipeline.

## Activation requirements

1. **Policy approved** for a separately versioned live release boundary. Keep
   raw and adjusted predictions explicit, and never rewrite historical replay.
2. Finish the cutoff-safe live MM inference adapter, with actual
   model-generated q/sub/duration and exact-11 validation; do not use
   synthetic q/sub as production inputs.
3. Use this candidate **only** on the source-scoped current GW
   (or separately verified explicit later-GW knowledge), write raw/gated
   provenance, and run end-to-end MM release regression checks.
4. Finish the original locked PM, TS and chip production adapters,
   and test a real GW before authorizing full release.

Current state remains **NOT_READY_FOR_LOCKED_LIVE_RELEASE**.
