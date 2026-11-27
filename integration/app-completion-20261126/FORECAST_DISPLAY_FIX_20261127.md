# Original forecast display repair — 27 November 2026

The user correctly observed that the public team pitch showed dashes instead of projections. The original MM/PM snapshot was loaded (674 players, GW12–17), but `shared-team.js` used `context.usable` both to authorize TS and to show individual xP/minutes. That flag includes the two-hour official live-status gate. With official news last observed at 04:56:15 UTC, the valid original snapshot was therefore hidden too. The earlier page/import tests did not assert numeric projections and missed this visible defect.

## Repair

Display eligibility now reuses the existing model-contract validator for the original six-GW MM/PM snapshot. Invalid/nonfinite/incomplete/future snapshots remain unavailable. A valid original snapshot supplies player xP, minutes, start probability and explicitly marginal draft comparisons, with its original computation timestamp. Expired snapshots are labelled historical. A visible warning explains why a new TS calculation is unavailable and that newer player status may be absent.

This display permission does not mutate `context.usable`, manager-state validation, TS client, forecast/news freshness gates, scorer, model versions or any forecast payload. Existing optimized team-control totals still require the original TS gate. No new forecast or recommendation is invented.

## Reviewed update of the existing preview

Actual current deployment: 8107588006, run 45982953612, SHA 65c380539f7bb08dab4d9e86f1b9373c00943a8c, publisher job 140452298109. Downloaded its actual artifact 15190108157, `app-completion-pages-45982953612`, 456,405,176 bytes. ZIP SHA-256 independently verified as `f0aecf1e4039613996ef0dfe845fa9b77fe0ce95dee35b4796c75fbea9e55281`.

Inspected all 3,882 files: the original 3,746 production files exactly match the prior review, plus the 136 existing isolated preview files. `baseline-preview-update-20261127.json` records that complete current artifact. Before building, every file must match. After building and immediately before publication, only the exact existing `previews/team-transfers-20261126/` subtree may differ; all production files remain immutable. The reviewed deployment/artifact identity guard remains active, including rejection of same-SHA later news deployments. No new app, branch, model or production merge.

## Regression checks

- Existing 15 JS and five Python contract/integration tests pass.
- Ten publication-contract tests pass, including a new strict-before-build/preview-only-replacement case.
- Helper regressions confirm that a TS-blocked valid snapshot remains readable without mutating the TS flag; invalid/future snapshots fail closed and expired snapshots are historical.
- The local-only synthetic Chromium renderer regression checks actual displayed numeric values: 15 cards with 1.25 xP/60 minutes per GW, 7.5 xP/360 minutes over six GW, while TS remains blocked and compute is never called. This is explicitly a synthetic UI test, not evidence of actual manager/model performance.
- After deployment, public verification must compare displayed one-GW/six-GW numbers against the original loaded model values for the actual imported XV, not merely assert that the catalogue/page loads. Aggregate receipts contain no manager player identities, prices, raw state or job capabilities; screenshots remain private.

## Published correction

Workflow [45989268115](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/45989268115) passed verification and protected publication. Deployment **8108442989**, code SHA **ff8a30fc8081899a4d385cf82e7993dbf8ba3b6a**. Same existing preview URL, no PR merge. The pipeline reverified all 3,746 non-preview production files unchanged; only the existing 136 preview files were updated. The renderer/helper/style URLs now carry content hashes so an ordinary reload obtains matching new files. The CI numeric renderer fixture passed, with stale TS still blocked.

The first CI attempt exposed a missing model-contract dependency in the sparse test checkout; the checkout now includes the existing model-interface module and reruns its 15 JS regressions too. No production permission or model change was required.

## Actual public numeric acceptance

After publication, a fresh Chromium session imported the actual official XV through the unchanged backend, without a fixture, injected cache or frontend routing. On **both** public Mit hold and Transfers pages, all **15** rendered xP and minute values matched the original loaded model for **each GW12–17 individually and their six-GW sum**. Original public forecast identity remains `79c047e172889aa517feab287b63c98606180c7e2ba691ddf784f1b93b19b1b1`, cutoff 2026-11-26T08:37:18.050176+00:00. This is the original snapshot, not newly calculated predictions.

Both pages show the computation timestamp, warning and versioned renderer, have no JavaScript exceptions or mobile overflow. The original TS gate remained false and the browser made **zero** TS computation requests. Aggregate proof: `evidence/forecast-numbers-public-20261127.json`. No player identities, raw manager state or capabilities are exported in the report. Screenshots stay private workspace deliverables.
