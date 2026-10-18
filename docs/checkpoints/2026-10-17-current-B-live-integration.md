# Current B → locked PM → private TS integration

Work continues from PR17 in PR18 (`integration-mm-live-20261017`). This is a
technical integration, not a new model selection or independent validation.
`locked_model_active=false`; the original production MM remains active.

## Implemented source chain

The current producer calls the original PR4 `bands_h42.0_C1.0` role code,
the existing PR8 `role_chance_return_duration` transformations, and PR9's NUM
feature contract. The original PR4 implementation is copied verbatim to
`scripts/pr4_individual_mm.py`. No artificial B profiles or legacy relabelling.

The role rebuild reproduces the final historical origin in each season:

| Season | Matched rows | Maximum P(start) absolute difference |
|---|---:|---:|
| 2024/25 | 784 | 6.80037e-10 |
| 2025/26 | 841 | 1.35622e-10 |

The 2025/26 source availability cap was initially missing from the restored
capsule; restoring the original strict-news join fixes parity. All NUM features
are separately compared to frozen PR9 rows. Unknown availability is not healthy
by default. Only verified prior squad/appearance evidence enters role histories.
Physical workload follows player identity across a transfer; same-club normal
role state does not. Current source news applies only to the origin GW. A
current DGW suspension requires fixture-scoped evidence rather than guessing.

The public checksum-verified role ledger preserves the upstream latent role
across refreshes and medical absence. It contains only public player/model
features, never manager state. The first publication has no invented
pre-injury forecast state. Unknown historic source publication clocks still
use the explicitly documented +3/+4-hour proxies and block certification.

## Minutes and uncertainty

MM expectation is `p*s + (1-p)*q*c`; appearance probability is
`p + (1-p)*q`. The bridge transfers the unchanged B p/q/s/c fields to PM while
preserving PM's original exposure controls and every non-minute propensity.
Formation selection changes the displayed XI, not B's marginal start chances.

The original PM sampler remains the default: rounded Gaussian starter
duration clipped to 1–90 (sigma 10), cameo clipped to 1–45 (sigma 7).
For a duration with upper bound U its analytic mean is
`1 + sum(k=2..U, Phi((mu-k+0.5)/sigma))`.
The application shows MM xM and this PM expectation separately. It does not
rescale points or silently change the sampler to force agreement.

In the first successful current run, the largest absolute analytic MM/PM mean
gap was **3.934172 minutes**. This is a disclosed diagnostic limitation.

The alternative PR17 PMF remains research-only. Its GW22 smoke replay has 546
matched rows, 7 fixtures, and 400 draws/arm:

| Sampler | xP MAE | xP RMSE | Simulated minus B minutes, mean |
|---|---:|---:|---:|
| Locked | 0.917560 | 1.783923 | -0.748064 |
| Experimental PMF | 0.923636 | 1.796601 | +0.047847 |

This reused small period does not justify promotion; it is neither an
independent calibration test nor evidence of better points accuracy. Live MM
output omits the PMF, minute-band estimates and quantitative intervals.
Uncertainty intervals are explicitly Not Available. Full research MM evidence
is archived separately for later rotation-risk/outcome analysis. TS has no new
risk parameters.

## Historical evidence retained

The existing 39,264-row historical replay is reproduced, not a fresh holdout:

| Metric | Original MM | B |
|---|---:|---:|
| Minute MAE | 11.240711 | 10.408358 |
| RMSE | 21.115962 | 20.172026 |
| Start Brier | 0.073445 | 0.068827 |
| Errors over 60 minutes | 1,559 | 1,278 |

B, B+XI, B+PMF display, and the combined contract preserve identical p/q/s/c/x
point forecasts. The existing uncertainty replay still reports 90.56% observed
coverage of the nominal central 80% intervals: it is not certified.

The historical 144-fixture unchanged-PM comparison gives xP MAE
0.918241 → 0.881045 and RMSE 1.845620 → 1.811052. Paired reported 95% intervals
for B minus original are [-0.045809,-0.027615] MAE and
[-0.045845,-0.023319] RMSE. Research reuse, partial source coverage and Monte
Carlo conditions remain material limitations. The original 2,125-point TS
benchmark is unchanged and has not been newly reproduced by this live run.

## Current execution evidence

First complete Actions run:
https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39053396513

- Official source cutoff: 2026-10-17T17:26:56.791117Z.
- 667 players, 60 fixtures, 4,002 player-fixture rows, GW8–13.
- Official origin deadline: 2026-10-23T17:30:00Z.
- Raw-source rebuild passes exact frame reproduction.
- Two complete B → locked-PM runs produce byte-identical MM and forecast JSON.
- Point components reconcile; all 120 club-fixture XIs have 11 players/one GK.
- All 173 source-marked OUT/SUSPENDED rows have zero xM.

First-run GW8 examples (not fixed control targets for subsequent refreshes):

| Player | MM xM | P(start) | P(plays) | PM E[min] | xP |
|---|---:|---:|---:|---:|---:|
| Haaland | 74.3914 | 92.1951% | 94.4514% | 73.5835 | 6.0150 |
| Saka | 83.5353 | 93.6426% | 94.8221% | 80.2628 | 6.2150 |
| Palmer (Chelsea) | 83.3463 | 92.3604% | 96.4383% | 79.8097 | 3.9125 |
| João Pedro | 75.3045 | 85.4143% | 86.0975% | 72.6752 | 4.0550 |

These figures precede the final source-cap/absence-label/role-memory hardening
and must not be represented as the final published snapshot without checking
its cutoff. No manual player corrections were applied.

## Private planning and production protection

POST `/preview/plans` loads only the sealed current B feed and runs the
unchanged original Python worker. The original `/plans` route remains
backwards compatible. Official prices, club, position, GW, freshness and full
content identity are checked before and after computation. Job capabilities
are private; bodies are not logged; input files are removed; results expire.

The preview reads the existing `fpl-manager-state-v1` local record and never
writes it. B plans/jobs have separate storage keys. A new forecast invalidates
old recommendations. Missing/stale manager state gives Not Available. No
official FPL action is performed. This browser has no actual manager record;
validation-only squad tests are not personal recommendations.

Backend controller deployment: `d2a73694ba1c5da5ce0ec66af04751bfce7df3cc`, Render
`dep-db9r2iajnfac73dba6s0`, confirmed live. Only controller and a pure content
integrity helper were transferred to the live branch. PM simulator, PM
conversion, transfer search, weights/rho/hit buffer and worker are preserved.
The public service health reports `supports_mm_preview=true`.

The Pages publisher overlays only `mm-preview/` on the latest successful
production artifact, verifies all other file hashes, and preserves immutable
forecast history. Scheduled code is pinned; failed builds never deploy. Cron
is `17 * * * *` on main; GitHub may delay schedule starts. A scheduled run is
not deemed verified solely because the cron exists.

## Tests and remaining gates

- Local full regression suite: **673 passed**, zero failed (38.71s).
- JavaScript B contract suite: **10 passed**.
- Actions historical validation at `2e3062f`: **671 passed**, historical MM,
  144-fixture PM and PMF smoke replay all successful.
- Real 667-player six-GW data also completes the original Python TS + FH/WC/BB
  path using a clearly marked legal validation fixture, without public state.
- TC current-half B scenario coverage is unavailable, so no invented TC timing.
- The browser has no actual manager-state: a personal result is not verified.
- No independent untouched evaluation period, complete historical source timing
  certification, or validated probabilistic minute intervals are available.
- BPS incompleteness remains quarantined; no missing values are invented.
- An earlier original-production TC extension run failed a floating-point
  comparison; later original scheduled forecast runs succeeded. That earlier
  failure is not evidence of a current continuous outage. The B preview does
  not reuse old-MM TC scenarios and no tolerance was relaxed.

Final publication/run/browser verification is recorded below.

## Same-cutoff current comparison after source-cap hardening

Successful hardened source run:
https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39054182018
Cutoff **2026-10-17T17:39:27.623816Z**. The public evidence artifact
`12109371181` has ZIP SHA-256
`275e2d830503619f6a77473154bce323011e4f99b1da63cf2f7bc60a35dd4a94`.

`analysis/replay_current_mm_integration.py` restores each original minute input
from that artifact, replaces only p/q/s/c/x with its actual B contract, and runs
both unchanged-PM arms over all 60 fixtures with identical seed/draw budgets.
The B arm reproduces every published xP exactly (maximum difference zero).
`analysis/results/current-mm-live-comparison-20261017/report.json` records the
complete comparison summary, code hashes and all 120 XI overlaps. Reproduction
also writes the full 4,002-row paired CSV. No actual manager is involved.

| GW8 player | Original xM | B xM | Original P(start) | B P(start) | Original xP | B xP |
|---|---:|---:|---:|---:|---:|---:|
| Haaland | 77.8033 | 75.3964 | 96.7196% | 93.5282% | 6.2225 | 5.9575 |
| Saka | 83.6289 | 83.5350 | 93.7524% | 93.6426% | 5.8025 | 6.5100 |
| Palmer, Chelsea | 84.5713 | 83.3486 | 93.8355% | 92.3634% | 4.2250 | 4.0825 |
| João Pedro | 78.2207 | 75.3080 | 88.7579% | 85.4185% | 3.6750 | 4.3250 |

Mean xM change is +0.09516 and mean xP change +0.002368 per player-fixture;
largest absolute xP change is 1.42. XI overlap is 11/11 for 66 club-fixtures,
10/11 for 48, 9/11 for six (mean 10.5). Every original and B XI has 11 players.
The generic leading GW8 point scorer changes from Haaland to Saka; this is not
a personal captain recommendation without a manager squad.

The changes include team-event interactions and 400-draw Monte Carlo noise;
identical random seeds do not imply event-aligned random numbers. A player can
gain simulated xP while losing a small amount of xM. These are forecast
differences, not demonstrated gains in future predictive precision.

The client integration verifier passes on all actual 667 × six-GW records,
4,002 fixture identities, 120 legal club XIs and 175 zero-minute/zero-point
hard-unavailable rows. It verifies every public file checksum, appearance and
minute expectations, hidden unvalidated intervals, expired deadlines and
changed-price rejection. The standalone B catalogue is derived from its own
verified official bootstrap; an outdated production catalogue cannot block a
fresh preview. Actual CI run/code provenance replaces the local-only label.

This source capture has **1,204 complete BPS action rows and 679 quarantined
rows**. Missing actions remain unknown, not zero-filled. These are current
counts, not the earlier GW7 audit's 334 rows.


## Final scheduled publication verification — 2026-10-18

Code pin: `8579df2de908cbed307c8e3bd69b0167dddc0ea2`.
Current source cutoff **2026-10-18T05:58:19.587177Z**, GW8–13, origin deadline
**2026-10-23T17:30Z**. All 667 players, 60 fixtures and 4,002 player-fixture
records are present. Forecast SHA-256:
`5688d08c5ed5251d2a66c1c0325867177105f9e836c59ff6cda60e66f57a8ae6`.

Four actual scheduled B refresh/publication runs are verified successful:
39102061804, 39084921121, 39077768949 and 39067312204.
Latest: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39102061804
The current compute job (117600181898) passed **673 Python tests**, **10 JS
contract tests**, **7 JS job-client tests**, raw exact reproduction, original
role/NUM parity and byte-identical repeat B/PM forecasts. Publication job
117602206059 verified **88 non-preview production files byte-identical** and
persisted the isolated preview. The public cumulative role ledger now contains
4,002 records. Cron remains `17 * * * *` on main, pinned to the code above;
actual launches were delayed and do not demonstrate guaranteed hourly service.

Browser verified:
https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/live.html?ui=20261017-1
The page reports the new cutoff and SHA verification. Player table, sorting,
filters, club XI and six-GW popup work. João Pedro's popup carries the same
cutoff, B p/q/s/c and unavailable uncertainty intervals. Current GW8 Haaland:
xM **82.68**, PM E[min] **79.50**, P(start) **92.2%**, P(plays) **96.0%**,
xP **6.32**, six-GW xP **34.89**. These are refreshed forecasts, not accuracy
results or targets to preserve. No application console errors were observed;
an unrelated Chrome extension metadata error was present.

Actual mobile end-to-end interaction is still **not verified**. Responsive CSS
inspection is not substituted for a real mobile test. No actual manager state
is present in this browser: personal transfers/captain are not verified.
The existing manager local-storage record is read-only to this preview.

Private service verification on a clearly labelled legal validation fixture
is recorded separately below. It is never the user's personal result.

### Private remote calculation status at this checkpoint

The deployed server completed a validation-only legal 15-player public-roster
state against the sealed B forecast on 2026-10-18. A result request without the
private capability was correctly rejected (404). The completed original Python
result has six GW actions, 15 lineup rows, one captain and one vice-captain;
TS and FH/WC/BB ran. TC scenarios remain Not Available. The actual deployed
result also passes the app plan renderer, including the actual-squad versus
proposed-plan sections. This is not a personal recommendation or a test of the
user's current manager-state. A metadata-only receipt is saved in
`analysis/results/current-mm-live-comparison-20261017/private-service-verification.json`.

The completed worker test identified missing propagation of the validation-only
label. A controller-only fix now preserves it through the unchanged worker;
both true and false cases have parametrized tests. Preview manager input also
rejects validation-only squads. Controller commit `e5ac3bf84038605bb2888ca81c76b217d7747735`,
Render deploy `dep-dba78cu1egvs739ks950`, confirmed live. No private capabilities,
squads, purchase prices or full results are committed.

The new preview view separates the original worker's current-squad XI from
the unexecuted transfer proposal, shows original returned GW/horizon totals,
repairs result navigation to the same snapshot, and styles the pitch/bank
sections responsively. Horizon validation also supports the truncated season
end; it does not change TS. Local full suite **674 passed**, plus **28 JS
preview checks** (10 contract, 7 job recovery, 11 personal view). Existing classic
manager, portable private import and new-GW draft-preservation tests also pass.

A private archived manager backup was located and read without public export.
It applies to GW7, not the present GW8 forecast. Updating GW, transfers, bank,
FT, chips or observation time is not inferred. The app preserves the saved
squad/prices and explains which current facts require manual confirmation.

Remaining certification gates: independent/prospective observations,
historical source timing and BPS coverage; no calibrated public minute
intervals. Remaining functional verification: an actual current manager-state
calculation and real mobile interaction. Full current-half B TC
coverage remains unavailable, so its future timing is Not Available/manual.
Production B activation is deliberately not performed.

## 2026-10-18 — existing classic app uses B in isolated preview

Executable integration source: `41161e4521a371bc4d0ddd94e2ed6d9dda13e6e1`.
Main schedule/publication pin: `730a29dceb35fa6ca7ccc18b8d125f34209b64cb`.
Existing UI is reused under `mm-preview/app/`; only display contracts,
snapshot identity and isolated private-plan routing are adapted. Production
PM sampling/math, TS/chips and manager worker are unchanged. Actual local
manager state/prices retain their original key; recommendations remain separate.

- CI **39129816821 success**: **684 Python tests +36 JS checks**, authentic
  B feature parity, exact raw rebuilds, current B→locked PM one match
  (**66 rows**), one GW (**667 rows**), six GW (**4002 rows/60 fixtures**),
  two byte-identical full forecast/MM outputs, protected-code diff clean.
- Cutoff **2026-10-18T13:08:01.101996Z**, GW8–13,667 players; sealed forecast
  `c77e040bbe29ffdf0130faac94e10c6c59e123298925b4494b9c01bf34f109f8`.
- Pages **39129820245 success**, persisted preview commit `940ddb1`;
  all **88 non-preview files** of the current production artifact unchanged.
- Public browser: classic navigation, player search/horizon/profile, Chelsea
  3-4-2-1 XI, fixtures, missing-manager My Team/Transfers/Chips and Model tree.
  Actual public B rows also pass the original XI renderer for all20 clubs.
  Haaland GW8:82.88xM,79.69 PM E[min],96.3% appearance,5.74xP; six-GW33.57.
  No app JS error observed; unrelated extension metadata errors excluded.
- URL: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/my-team-classic.html?ui=fef499563f07e0c1

Remaining: actual current manager state is unavailable in the test browser;
no user transfer recommendation is claimed. The normal browser's same-origin
saved state is reused, never inferred from the old GW7 backup. Some preview
team-goal/per-match-history fields are Not Available: the former legacy
fixture-expectations source is deliberately not mixed into B, and the latter
requires a matching display snapshot. Existing model tree remains the original
reference explanation, not a newly certified B-calibration explanation.
Physical mobile interaction and independent certification remain unverified.
`locked_model_active=false`; production B remains inactive. No further research.
