# B player probabilities — 19 October 2026

The B preview now has a compact all-position overview (xP, xM, start probability per fixture, six-GW xP) and a player dialog. The dialog shows each fixture separately, opponent and kickoff in Europe/Copenhagen, with a six-GW selector. It supports keyboard dismissal, explicit close, mobile scrolling and preserved table filters.

Each fixture exposes:

- P(no minutes), P(cameo without starting), P(start), P(60+), P(90).
- Exclusive minute bins: 0, 1–59, 60–89, 90; these sum to one.
- P(points ≥ 2), P(points ≥ 5), P(points ≥ 10).
- Central empirical 10th–90th point quantiles and PM expected minutes.

Start, 60+ and 90-minute probabilities overlap. A points interval describes predictive outcomes, not a confidence interval for xP. Probabilities and intervals are not independently calibration-certified. Point and outfield probabilities use 400 draws; small probability differences should not be overinterpreted. GK minute probabilities and mean use the already validated exact joint distribution, while point probabilities use its sampled PM trajectories.

## Implementation boundary

`src`, `model`, and `service/manager_job.py` are byte-identical to the prior validated role-aware GK v2 implementation (`cd1af40`). The new `scripts/pm_preview_distributions.py` calls the existing aggregate simulator and replays its same seed through the existing match sampler. Each player’s replayed mean points and minutes must exactly equal the existing aggregate before anything is exported. The extra replay costs computation but leaves the locked PM source and RNG semantics untouched.

Current six-GW forecasts include distributions inside each fixture and the sealed forecast hash. Historical replay defaults remain unchanged; distribution replay is enabled only for the current preview and its one-match/one-GW validation. The stage validator now compares all distribution fields exactly with the six-GW output. The UI checks probability ranges, exclusive mass, threshold ordering, minute bins and interval validity in addition to its existing checksums, freshness/deadline and GK physical constraints.

There is no new fit, role calibration or change to the prior GK-v2 hierarchy correction. No personal manager state is required, stored or published by the player panel. Original TS remains unchanged.

## Validation

Source: `150695746949e5f405b3af944e4b53e2f96c2af4`.

- All 713 Python regression tests passed locally and in the dedicated exact-source GK workflow (39263488944).
- Existing preview/privacy JS contracts and new PM probability contract checks passed.
- Locked PM exact seeded parity passed for 100 fixtures and a 100-draw aggregate; all fields match the retained original reference.
- Local actual-data six-GW output: 668 players, 60 fixtures, 4,008 player/fixture distributions. Desktop/mobile Chromium checks passed, including goalkeeper and rotation-outfield panels, six-GW selection, source checksums, exclusive mass, ordered point chances, Escape/button close, mobile point-card scrolling, no page errors and no localStorage writes.
- Same-input local v2 reference: all existing xP, sampled minutes, point-component and penalty-miss fields exactly match across all 4,008 rows. Earlier-reference MM refit runtime differs at less than 1.4e-8 minutes; this is not presented as byte-identical MM controls.
- Full exact-source publication validation: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39263489281 — passed.

Local browser checks used actual current model output plus retained public reference evidence; their fixture is not the final publication artifact. The checks were then repeated successfully against the deployed public artifact in desktop and mobile Chromium, with TLS verification enabled. Both goalkeeper (Penders) and rotation-outfield (J.Timber) panels worked; all 4,008 distributions validated, all six GWs were selectable, the mobile point cards were reachable, both dismissal methods worked, and no page errors or localStorage writes occurred.

## Publication

- App: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/gk/
- Successful deployment: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39268993285
- Main publication-pin-only commit: `7ec5b95d14d51d403fb9061b182f784bb85d6770` (exactly two preview workflow files).
- Validated sealed forecast: `a3afdde6b231589058c551bb742c175855abb3e907f79d7f78690807a08358b0`.
- Original B/PM source clock: 2026-10-19 13:59:43 UTC; official GK capture: 14:09:12 UTC.
- Public receipt: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/publication.json
- All 88 production files are byte-identical to production artifact 12190516176 / run 39258433041. `locked_model_active=false`; only the isolated preview was replaced. Hourly preview publication now points to the same validated source.

Current Penders first fixture: xM and analytical PM E[min] 89.4687, P(start) 99.7593%, P(60+) 99.2787%, P(90) 98.7665%, xP 3.77. The new sampled point probabilities are 83% for 2+, 33.5% for 5+, and 3.25% for 10+, with empirical central interval [1,7]. These refreshed-input point values must not be treated as a same-input model comparison with the previous morning's published forecast.

