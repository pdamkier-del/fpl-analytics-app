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
