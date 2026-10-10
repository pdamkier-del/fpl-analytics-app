# Live availability boundary — approved and wired to MM exporter; full live chain blocked

Date: 2026-10-10. Continues [the live integration checkpoint](2026-10-10-live-final-integration-checkpoint.md).

## Decision needed before release

The **frozen** `run_mm_unified_official_roles.compose` is unchanged:
`xmins=p_start*start_minutes+(1-p_start)*q_sub*sub_minutes`.
The historical `run_mm_v2_team_news_availability_experiment.py` runner
caps `p_start` at zero for OUT/SUSPENDED but leaves `q_sub` untouched.
Thus frozen raw forecasts may include positive cameo minutes for a certified
unavailable player, violating `mm_release.validate_mm_release`.

The **approved, separate live availability boundary** is available at:
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

## Implemented production export wiring (2026-10-10)

The actual MM release CLI `scripts/export_mm_release.py` now enforces
`--live-hard-availability` for any non-historical season. Legacy 2025/26
historical replay behavior remains unchanged. No silent zero-minute rewrite
is possible through the current-season exporter.

**Prerequisites**: genuine completed locked MM inference output, including
`p_start`, `xmins`, `start_minutes_mean`, model-derived `mm_q_sub`,
model-derived `mm_sub_minutes`, team_news_state and availability caps;
an official Team News ledger captured before the forecast cutoff, scoped
to the **same target GW**, with one verified observation per player.

The 2026/27 source collector already writes the required native official
Team News file to
`data_v1_1/derived/team_news_audit/2026-27-v2/predeadline_strict.jsonl.gz`.
The exporter accepts the original JSONL.gz directly (no lossy conversion).
When a real MM inference artifact exists, the next step is:

```sh
python scripts/export_mm_release.py \
  --input work/live-final-model/mm_frozen_raw.csv.gz \
  --out work/live-final-model/mm_release \
  --model-version fpl-model-2026-10-09-assembled \
  --season 2026-27 \
  --origin-gw 6 \
  --news-ledger data_v1_1/derived/team_news_audit/2026-27-v2/predeadline_strict.jsonl.gz \
  --q-sub-col mm_q_sub \
  --sub-minutes-col mm_sub_minutes \
  --live-hard-availability
```

The `--input` path above is **an expected future artifact, not an
existing output**. Do not create fake/simplified MM outputs to make this
command succeed. The command fails if any official news observation is
later than the forecast cutoff, is unknown/unverified, mismatches the
frozen MM player state, or targets another GW. It also fails if the
original MM xMins do not equal the unchanged `compose()` result.

A successful exporter writes `mm_forecasts.csv.gz`, original
`manifest.json` and `live_availability_policy.json` with hashes of
the raw MM prediction, source Team News and adjusted release artifact.
Model-level raw `mm_raw_xmins` and effective cameo inputs remain in
the forecast CSV for audit.

**Final release verification is now wired:** The main
`scripts/publish_final_model.py` refuses to certify even a hypothetically
complete MM → PM → TS/chip chain unless the chain manifest includes:

- `availability_policy_path`: repo-relative path to the exported
  `live_availability_policy.json`
- `availability_policy_sha256`: exact SHA256 checksum of that JSON

Its `mm` component SHA256 must equal
`live_availability_policy.json.published_mm_sha256`; its
`next_gw` must equal the official news origin GW, and its model
version and news coverage must match. This prevents accidentally
releasing raw, uncorrected MM outputs.

[Approved exporter and release-gate CI tests](https://github.com/pdamkier-del/fpl-analytics-app/actions/workflows/availability-boundary-proposal.yml)
are contract tests, not an executed current-season MM/vFinal forecast.
**The final model remains blocked** until the actual frozen MM inference
and downstream PM/TS/chip adapters are complete.
