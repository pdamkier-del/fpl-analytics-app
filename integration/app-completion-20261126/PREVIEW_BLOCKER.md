# Preview release status

**Resolved:** the isolated preview was published and verified on 27 November. See `PUBLIC_PREVIEW_20261127.md` for the working URL, successful run and remaining original TS data-freshness constraint.

Update 2026-11-27: the owner allowed this integration branch in github-pages and dispatched run 45981181923. The prior environment-policy blocker is therefore resolved. That run correctly failed the old pinned-baseline guard because production had advanced.

The replacement baseline is based on the actual successful deployment and downloaded artifact, not an unchecked SHA update. See `BASELINE_REVIEW_20261127.md` and `baseline-20261127.json`. Exact deployment/artifact/file checks remain mandatory. Publication uses the same protected job with both preview flags; no permission change or bypass is part of this update.

Historical policy rejections: runs 45827817575 and 45827877728. Historical read-only verification: run 45831222611. These do not establish current public preview availability; see the PR's latest deployment receipt.
