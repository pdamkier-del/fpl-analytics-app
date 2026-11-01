# One established, available goalkeeper: B preview v2

## Change and scope

The v1 bridge assigned the complement of a keeper's raw MM start probability to an unlisted group. That residual could be about 40% despite the player being the documented deputy to an injured first choice. V2 separates evidence of a real competing role from mere squad registration. This is an explicit preview change; production model/scoring/TS code is not activated or changed.

V2 applies a narrow correction only when all of these hold at the forecast cutoff:

- At least three prior fixtures have a verified goalkeeper pair; consider the most recent five fixtures within 90 days.
- Exactly one keeper from those squads, or from earlier starts within 90 days, remains potentially available. Missing availability is uncertainty and cannot remove a competitor.
- That sole keeper is represented in the forecast, has an explicit full availability cap and AVAILABLE/RETURNED_AVAILABLE news state, and already has positive MM start mass.

Returning former starters remain competitors even after missing all five recent squads. Recently selected unlisted keepers remain competitors rather than being assumed unavailable. Missing evidence, doubtful fitness or several established competitors leaves the existing B/v1 distribution in place.

For a qualifying team, the remaining candidates jointly receive a historically estimated novelty probability; existing MM relative weights split this small aggregate mass. Adding names to a squad does not multiply it. No player/club-specific probability or Penders exception exists. The GK starter/substitute process, duration distributions, scoring rates and joint 90-minute coverage are reused unchanged from v1.

Explicit season-long goalkeeper loan news is carried through all six forecast GWs, including reserve minutes. Unknown injury recovery dates are not invented: future-GW forecasts still inherit B's conditional availability assumptions and must not be read as confirmed medical returns.

## Historical probability and uncertainty

Fit uses 2024/25 only. Before each historical deadline, the model identifies established keeper roles from verified past squads/starts and compares the next actual starter with that set. Contradictory hard-out training labels and missing/ambiguous actual starter labels are excluded; validation retains the complete matched cohort.

There are 660 valid population contexts, with three starters outside the available established set. Jeffreys smoothing gives population novelty rate `(3 + 0.5)/(660 + 1) = 0.00529501`. Among six qualifying sole-candidate contexts, none had a different starter. Using the project's existing shrinkage strength five:

`P(other starter | sole established candidate) = (0 + 5 × 0.00529501)/(6 + 5) = 0.00240682`.

The sole candidate therefore receives 99.759318% start probability. This is a posterior predictive mean, not a guarantee of selection. The exported conditional empirical-Bayes interval does not include uncertainty in the estimated population rate. Six training examples and two affected validation fixtures are insufficient for independent calibration certification.

## Validation

Fit is frozen on 2024/25; the expanded MM comparison covers 2025/26 GW6–38, 330 fixtures and 3,010 GK rows. This includes an early-season injury transition absent from the narrower PM cohort. The period was previously used for project research; it is not an untouched independent holdout. Existing historical kickoff-delay known-at proxies are retained.

| MM metric | v1 | v2 |
| --- | ---: | ---: |
| Start Brier | 0.02485390 | 0.02473508 |
| Minute MAE | 4.99479283 | 4.96494124 |
| Minute bias | 0.00099668 | 0.00099668 |
| P(60+) Brier | 0.02593302 | 0.02581337 |
| P(90) Brier | 0.02669756 | 0.02657767 |

Only two team-fixtures, comprising ten keeper rows, qualify: Mamardashvili with Alisson hard-out in GW7, and Petrović as the sole established available keeper in GW20. Woodman/Pécsi in the first case and Forster/McKenna in the second do not receive large start shares merely from registration; Forster has unknown news state rather than being falsely marked injured. In that affected subset, start Brier is 0.03576889 → 0.00000184 and minute MAE 9.20714798 → 0.22182011. The model does not rewrite ordinary multi-keeper competition to obtain an aggregate improvement.

The frozen PM comparison remains 2025/26 GW22–38, 144 fixtures and 1,361 GK rows. No qualifying role-change case lies in that interval. Identical PM inputs therefore reuse the exact v1 draws: xP-MAE 0.56352314 and bias -0.02416605 are unchanged. This is a point-regression result, **not evidence that takeover xP accuracy improved**. No new PM rate model or synthetic historical point forecast was created to fill this coverage gap.

All analytical team goalkeeper minutes remain exactly 90. Existing and new tests exercise realized single-GK coverage, one starter per team, MM/PM matching, returning starters, unlisted recent squad members, future-observation exclusion, target-outcome exclusion, missing news/availability, doubtful sole keepers and season-long loan exclusions. The original PM default/event/scoring parity guard remains in place.

## Current sources and deployment

The same direct official Chelsea squad, injury, coach, lineup/report and player-profile sources from the preceding audit are refreshed, with per-source UTC retrieval times, page publication fields and SHA-256. The actual current verified squads, including internal provider identities for unlisted keepers, are sorted, hashed and archived in the validation artifact. Provider identities are not fabricated FPL players or individually published point predictions.

For Chelsea's next fixture, Martinez's current hard injury exclusion, Sanchez/Jorgensen's explicit season-long loans and Penders' verified squad role allow the correction. Sharman-Lowe and Slonina remain potential outsiders with a small collective probability; their registration alone no longer receives the entire raw MM residual. The coach's trust statement corroborates the evidence review but is not converted into a hand-picked numerical coefficient.

The public comparison is v1 versus v2 with the **same fresh source inputs, duration PMFs, event rates and seed budgets**. This avoids confusing a source refresh with a model improvement. Final exact-source CI, publication, readback and browser results are recorded below after validation.

## Exact-source CI and fresh-input comparison

[Full chain run 39211805359](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39211805359) passed for code `c90491b07828d7e13e877eb5e5977c0c32a21ca7`. [Separate run 39211805428](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39211805428) passed all 712 Python tests, original B JavaScript/privacy checks, joint GK contracts and original-PM seeded/default parity. Full-chain historical results reproduce the metrics above.

Fresh current chain: 668 players, 60 fixtures, GW8–13, 120 team-fixtures. Forecast/MM/audit repeat is byte-identical; one-match (66 rows) and GW8 (10 fixtures, 668 rows) exactly match the full-horizon outputs under shared fixture seed offsets. The unchanged TS completes its six-GW regression on the actual forecast using an explicitly synthetic legal state; manager state is unchanged, no actual user plan is published, and chips are not exercised in this stage. All eleven explicitly season-loaned GK forecasts have zero minutes and points throughout the horizon.

Original B/PM source cutoff: `2026-10-19T06:55:57.376409Z` (08:55:57 Copenhagen). Official source capture: `2026-10-19T07:05:26.150448Z` (09:05:26 Copenhagen). These are fresh v1/v2 comparisons on identical inputs, not a comparison of different source days:

| Penders GW8 | Same-input v1 | v2 |
| --- | ---: | ---: |
| P(start) | 57.939581% | 99.759318% |
| xM | 52.095406 | 89.468664 |
| PM analytical E[min] | 52.095406 | 89.468664 |
| P(60+) | 57.683951% | 99.278744% |
| P(90) | 57.362969% | 98.766518% |
| xP (400 draws) | 2.3425 | 3.8375 |

The other group's start mass is 0.240682%; its expected minutes include both rare starts and injury replacements, preserving exactly 90 team minutes. Neither the starter chance nor the minute distribution is forced to 100%/90. The current availability premise matters; future medical returns remain conditional.

Sealed snapshot: `d19e6b0ba796e86f21500b0f90a53afcc7e7ca8e16647a5ba3769a5f28c4f3b8`. Archived role-squad CSV SHA-256: `0446b6bcce600d3b72c201b16d030ff52da6390f9a60196abcf4c6daada76f15`; decompression/readback matches the forecast receipt. Main configuration commit `898a2e80a540c683c2516739cb2a4e87717ca9c8` changes only the two preview source pins, not production model/application code.

## Published and browser-verified

[Live B preview](https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/gk/) was deployed by [Pages run 39215313291](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39215313291). All nine public GK files (forecast/MM, v1/reference data, evidence, index and frontend files) were downloaded and matched the exact validated artifact byte for byte.

Real Chromium checks with TLS verification passed at desktop 1440×1000 and mobile 390×844: v2 version/checksums, Penders' 89.47-minute row, v1/v2 comparison, GW8→13→8, Chelsea filtering, future Sánchez loan exclusion/zero minutes, nine official source links, no JavaScript page errors and no localStorage writes. Existing B/live, overview and evidence navigation returned HTTP200. Screenshots were inspected.

The [public receipt](https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/publication.json) reports validated source `c90491b07828d7e13e877eb5e5977c0c32a21ca7`, production run `39208688429`, artifact `12167147633`, all **88 production files identical**, and the experiment's `locked_model_active=false`. No production model/application code was merged or activated. Scheduled preview refreshes now use the validated v2 source.

Result: Penders' documented deputy role now produces near-full-game expected minutes rather than a large unsupported competitor residual. Historical MM direction and all regression/coverage gates pass, while the sparse affected cohort and the limited historical xP coverage remain explicitly disclosed.
