# MM integration delivery checkpoint — 2026-10-17

**PREVIEW READY – NOT YET CERTIFIED.** Do not lock or activate the candidate.

## Verified deliverables

- App: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/
- Draft PR #15: https://github.com/pdamkier-del/fpl-analytics-app/pull/15
- Model/source correction: `d8e5337`; computed evidence: `79c65d4`.
- [Validation39013829273](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39013829273): **89 tests**, actual B refits at50 origins, six-arm common replay, all39,264 player-fixtures/40 club-seasons and immutable production/frozen-data checks.
- [Deployment39013859364](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39013859364): **success**. Existing main-only Pages environment rules were respected, not changed.
- Public preview path commit `2ab6558`: all53 changed paths are under `app/mm-preview/`. Publication reuses original forecast artifact12092663747/run39011647304 and verifies all**88 other production files byte-identical**.

## Results and actual tolerances

| Model | Minute MAE | RMSE | Start Brier | Errors >60min |
| --- | ---: | ---: | ---: | ---: |
| Original | 11.240711 | 21.115962 | .073445 | 1559 |
| B /common candidate | 10.408358 | 20.172026 | .068827 | 1278 |

The historical common contract preserves frozen B p/q/s/c/x exactly. The real B fitting entry point has latest clean-CI maximum difference **2.0374774578613142e-7** against frozen B across39,264 rows, within absolute tolerance**1e-6**. Earlier local and another CI run matched exactly; that does not imply bitwise identity on every numerical platform. PMF expectation max residual**2.842170943040401e-14 minutes**.

Earlier local/clean-CI CSV reproduction compared13 contents, aligning tied top100 records by canonical keys: max numeric difference6.22169e-13 (tolerance1e-9). Codec/container bytes are not claimed identical. The latest artifact12094027486 has GitHub-reported digest`sha256:4bd38158ddbd672a7e017ddfd2a8a07ae9973b2f9bc929d94c957a9342b021e1`; it was retained on GitHub, not independently downloaded again after the workspace interruption.

The legal formation output still has101/660 exact XIs (15.303%) and43.939% >=10. Positions are historical classifications and selected slots, not independently certified in-match tactical truth. Equivalent2024/25 formation evidence remains missing.

## Browser tests actually performed

Both the previous and refreshed public Pages versions were opened. Canonical names now resolve reserves and2024 players through the checksum-verified identity registry rather than using the starter-role ledger alone. No probabilities/minutes were changed by this fix.

Tested: Pitch/List, name/start/xM sorting, both sort directions, player popup, unavailable0-minute profile, season/GW/club selectors, all20 clubs, compressed-snapshot SHA verification, reload and explicit2024 formation Not Available. No app-origin JS errors were observed; browser-extension metadata errors are unrelated.

Mobile test used the same published app in a390px iframe (client/scroll width375px including scrollbar), with no document overflow; popup and sorting worked. This is **not physical iPhone/Safari certification**.

## Gate decision and remaining blockers

B's MAE/RMSE/Brier/tails remain intact. Formation selection does not nudge start probabilities. The uncertainty gate fails: central80 coverage90.56%; shortest80 coverage87.67%; exact-mean correction slightly worsens CRPS/logloss. Uncertainty therefore remains experimental, not validated.

Still missing: genuinely untouched later evaluation; historical actual publication clocks; resolution of35 hard-source conflicts; review of the three B club-risk flags; comparable2024 position/formation coverage; calibrated/non-inferior PMF; verified current-season PR8→B feature/provenance bridge. Current B forecasts are deliberately **Not Available**. No unapproved B point/transfer recommendation was fabricated.

Core coverage was audited with a checksum-verified, read-only identity/minute query:2022/23–2025/26 exist, but earlier years are not later locked-parameter holdouts for a model selected in2024/25. See the adjacent Core audit JSON.

The candidate validation pipeline ran MM only. The existing normal scheduled original-model workflow ran independently (39011647304, event`schedule`, success) with its unchanged original PM/TS; it was not a candidate downstream A/B test. GitHub's cron expression does not guarantee exact-minute start times.

Production MM/PM/TS/chips and benchmarks remain unchanged. `locked_model_active=false`. No official transfers or private manager-state writes.

## Publication and rollback

The reviewed gateway on`main` pins the validated source and waits for a quiet verified publication window. Only public historical preview files are persisted to the live branch, preserving them through subsequent ordinary forecast publications. Do not remove or weaken Pages environment protection to deploy research branches.

The obsolete gateway on the live branch was removed in`bdb07e5`; it is recoverable from Git history. The working gateway remains on`main`.

Rollback only the public preview path commit/revert and republish the last verified production artifact under the existing publication lock. Production model code needs no rollback. Keep research evidence and draft PR intact.

Full mathematical/error/calibration report: [research report](../research/2026-10-17-mm-integrated-preview.md). Structured completion evidence is adjacent JSON; complete replay CSV/JSON remains in`analysis/results/mm-integration-preview-20261017/`.
