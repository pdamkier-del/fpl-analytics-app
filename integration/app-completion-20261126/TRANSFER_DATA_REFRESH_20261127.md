# Transfer calculation blocked by stale public inputs — 27 November 2026

## Diagnosis

The original private Python service is healthy and supports the unified B/snapshot/chip runtime. The public MM/PM forecast is still the original 2026-11-26 08:37:18 UTC snapshot (identity `79c047e172889aa517feab287b63c98606180c7e2ba691ddf784f1b93b19b1b1`). Official public status is from 2026-11-27 04:56:15 UTC and exceeds the existing freshness gate. A direct fresh official bootstrap comparison also found **10 changed player prices** among the same 674 identities; GW12/deadline still match. Refreshing only a status timestamp cannot safely unlock transfers.

The UI's read-only original xP remains valid as a labelled snapshot. A new TS plan requires a new original capture with current market data, not a fabricated recommendation, edited prices in the old forecast or a relaxed safety check.

## Existing numerical producer, unchanged

Started existing validation-only workflow run **45993529455** on the existing stable integration ref. It uses source **d7060b51cf16016f7947b2ffc110909afea89bb7**, the source that produced the current public data. Independently matched all **20** `forecast.code_sha256` entries to that exact Git source. No MM/PM/TS implementation, fitted-policy selection, weights or numerical configuration was edited. The normal workflow captures official inputs and performs its existing deterministic repeats and release gates. This wrapper's validation flag prevents its old app publisher from running.

## Minimal public-data integration

The existing PR #60 workflow has an opt-in `current_data_run` input, used with both existing preview flags. It requires a completed successful exact wrapper/numerical job and the existing `mm-current-live-preview` public artifact. The ordinary UI-preview mode remains available. Providing this new input without preview mode cannot accidentally run the legacy model/publisher jobs.

`refresh_data.py` validates the new source against the old model/code/version/scenario-policy metadata, content seals, original current/gk/index hashes, full six-GW identity and the actual current official next-GW/deadline/674-player price/team/position catalogue. The original fresh sealed status must match too. Only existing public JSON/CSV/GZ data under `mm-preview/current`, `mm-preview/gk`, `mm-preview/news` may be copied; original immutable history cannot be changed and no file is deleted. All production app/UI/JS/CSS/root files remain byte-identical. Only the existing isolated preview may receive its reviewed orchestration patch: automatic job resumption waits for the official XV, and re-confirming completely identical manager facts preserves the original private state hash instead of invalidating an in-flight plan merely by changing observed_at. Any other state field or future/invalid timestamp still prevents that reuse. The original numerical payloads are copied, not recalculated or patched in the integration.

A reviewed full baseline of deployment **8108442989**, artifact **15193226764** from run **45989268115**, is in `baseline-transfer-data-20261127.json`. Actual ZIP SHA-256 `01cf8105985f2dc5a82ea3b70f12d05693d601a7a0267a52a9b8aa0a62e92f9c` was independently verified and all **3,882** files inspected. All original 3,746 production files still match the earlier review.

The protected Pages publisher retains the exact deployment/artifact guard, revalidates current official data immediately before publication and requires the complete tested site to match its candidate checksum inventory. It does not merge PR #60 or deploy a new backend/model.

## Permanent recovery and privacy

Before replacing public data, `preserve_pages.py` stores the exact original public Pages TAR and complete reviewed manifest in GitHub Releases and downloads it again to verify recovery. The newly generated public Pages TAR/manifest is preserved and recovered too, before deployment. No overwrite flags are used; provider checksums must match. Existing temporal Actions retention is therefore not the recovery dependency for either revision.

A local attempt to upload the original snapshot with the managed user's upload credential returned HTTP 401 and made no published release. Preservation uses the existing protected Actions mechanism's repository-scoped `contents: write` token instead; archive/recovery failure stops data publication. This permission is only used for public archive assets, never private TS information.

These recovery records are public-data backups, not a parallel model producer or an assertion of C1 protocol eligibility. They do not alter PR #54's validation, protected substitutions or any research outcome. Actual manager inputs/results/capabilities remain in the existing private service and browser, never Pages/Git/CI artifacts.

## Tests and operational limit

Nine synthetic data-publication tests cover official price/status/deadline changes, source/configuration mutation, checksums, exact producer provenance, UI/history preservation, unsafe paths and TAR recovery inspection. Existing contract tests and browser/renderer regressions are retained.

This is an explicit refresh through the current integration workflow. Automatic main-branch publication/source-mirror coordination still needs C2 release review; no PR/main merge or new scheduler is introduced here. A later scheduled publisher must preserve the actual latest Pages baseline and this preview, and may not overwrite newer data with the older generated mirror. Existing newer-forecast/deployment guards continue to reject such a rollback.
