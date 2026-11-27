# Public preview verification — 27 November 2026

**Later display correction:** see `FORECAST_DISPLAY_FIX_20261127.md`. Run 45989268115 now publishes numeric original MM/PM projections independently of TS readiness. Actual public one-GW/six-GW values were verified for all 15 players on both pages. The release receipts below describe the earlier deployment.

**Preview:** https://pdamkier-del.github.io/fpl-analytics-app/previews/team-transfers-20261126/app/overview.html

**Transfers:** https://pdamkier-del.github.io/fpl-analytics-app/previews/team-transfers-20261126/app/transfers-classic.html

**Catalogue:** https://pdamkier-del.github.io/fpl-analytics-app/previews/team-transfers-20261126/app/players-classic.html

Published through the existing protected workflow with both flags enabled: [run 45982953612](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/45982953612). Both `app_completion_verify` and `app_completion_publish` succeeded. Deployment **8107588006**, tested code SHA **65c380539f7bb08dab4d9e86f1b9373c00943a8c**. PR #60 remains open and unmerged. Other forecast/model computation/publication jobs were skipped.

## Preserved production

The builder and final publisher guard independently verified all **3,746** files against the reviewed actual production artifact. Only **136** files under the isolated preview prefix were added. The public `.nojekyll` marker survives artifact transfer. Original model/scenario/configuration/source files were not edited or recomputed; all newer production root files remain present. The reviewed input artifact and full inventory are documented in `BASELINE_REVIEW_20261127.md` and `baseline-20261127.json`.

## Tests and public delivery

- 15 existing JavaScript contract tests and five existing Python integration tests passed.
- Nine new publication-contract regressions passed; draft/legality/budget/data-root helper assertions also passed.
- Chromium prepublication checks passed on the full artifact, with manager-backend unavailability explicitly injected and no private payload in CI.
- Independently fetched every one of the **136 public preview files** and compared its SHA-256 with the locally built bytes. All matched. Thirteen selected original public files also matched, including current index/news/publication, TS client/guards/importer and root diagnostic/HTML/service configuration.
- Fresh public manager import also completed through the real unchanged backend (history POST 202, subsequent polls 200), without cache injection or fixture. Verified 15 players, legal XI plus four substitutes, seven period options, the same XV on Mit hold and Transfers, draft replacement/reset and unchanged actual manager-state. Original manager-state validation passed; no JavaScript exceptions. See `evidence/public-manager-verification-20261127.json`.
- Opened all three public URLs directly in Chromium with no frontend routing, backend substitution or manager fixture. All returned HTTP 200, original forecast catalogue loaded (674 players, GW12–17), no page exceptions, no mobile horizontal overflow. This public check is distinct from the unavailable-backend CI test.

Machine-readable aggregate receipts are in `evidence/`. Actual manager payloads, browser storage, job capabilities and screenshots are not published in Git, Pages or CI. Screenshots are private workspace deliverables only.

## Remaining original service constraints

The published official status was observed at **2026-11-27 04:56:15 UTC** and exceeded the unchanged two-hour guard during verification. A real TS plan therefore remains unavailable until the existing status producer refreshes it. No recommendation, expected team gain or relaxed freshness rule was invented. The existing full-history backend can take time on a first import. See the separate aggregate public manager check for what was actually observed; page/asset delivery does not imply TS acceptance.

A later publication must review whatever deployment/artifact is current at that time. This one-time baseline intentionally rejects newer deployments, including same-SHA news publications. No automatic future production approval or PR merge follows from the preview.
