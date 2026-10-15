# Dynamic PM v2 completed — 15 October 2026

PR #3, branch `model-audit-optimization-20261012`, base `0e1117d`. No production merge/deploy or private manager data. Production parameters, original MM/PM/TS/chips and benchmark2125/44 transfers/28 hit points unchanged; `locked_model_active=false`.

## Completed

* Eighteen development configurations: fixed75, minutes and xG-contribution-weighted reliability, conditional uncertainty, correlated-error moments, regularized/hierarchical gates. Selected `detailed_20` (amount), validation xG deviance0.34586850 versus0.34786894 fixed75.
* Numerical code72b61e4, run38772814007: all38 jobs successful.36 shards/24 model-season cells;3,168,000 match draws,2,376,000 legal-XI draws. Frozen public captures from38729720330. Original independent xP exact; fixed75 prior candidate reproduced; point-component sums and complete matrix checked.
* Locked-MM legal-XI point MAE original/fixed/amount:2024 .94690424/.94626021/.94720527;2025 .92630070/.92519343/.92645657. Selected dynamic is not robustly better. Uncertainty gate has tiny, statistically uncertain MAE gains and mixed RMSE. Experimental-MM interaction is inconsistent.
* Source9fac2d1, run38774188162: six-seed/fixed-fixture diagnostics (86,400 additional draws), exact Shapley error attribution and deadline checks passed. Residual endpoint correlation~.973/.977, not independent errors. Gamma conditional profile variance is not total predictive variance.
* Corrected reporting140387a, run38777082642: saturated any-new-player/absence flags replaced by development-median start-mass fractions; sparse-group inference warnings. Existing simulations were reused unchanged. All11 exported source JSON SHA-256 values verified byte for byte. Full reports and manifest are in `analysis/results/dynamic-pm-v2-20261015/`.
* Local547 tests pass (31.07s). Full audit38774188180 at9fac2d1 passed546 tests (29.93s), JS checks, original reproductions and benchmark preservation. Reporting adds one further local regression; later automatic audits are separate and not pre-counted as passed.
* All60 preexisting source files match0e1117d byte for byte. Preservation hashes saved. New work is additive research only.

## Decision and limits

Do not promote dynamic weights. Preserve fixed75 research reference and original production. Large XI marginal projections (22.05pp/62.39pp under locked MM) are a separate MM/input issue; PM arms have identical legal probabilities within comparison. Legacy OG/CS physics is identical across arms, not newly certified. All historical duration-clamp counts were zero.

Inherited publication-time proxies, real medical/tactical/summer-transfer labels, reused evaluation periods, incomplete full six-GW TS origins (33/183 cells), MC precision and raw Actions capture retention remain limits. No candidate TS total or live certification is claimed. Legal-exposure-aware gate fitting would require a new predeclared experiment and fresh validation.

See `docs/audits/2026-10-15-dynamic-pm-v2.md` for mathematics, all controlled tables, CIs, mechanisms and reproduction commands. **Do not restart the expensive primary or MC matrix merely to recover reports:** read the committed JSON/manifest or completed evidence runs above. Source/analysis/numeric commit roles are deliberately separate.
