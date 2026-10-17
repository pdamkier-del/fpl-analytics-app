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
- The original production's separate TC extension job has a floating-point
  comparison failure; the new B preview deliberately does not reuse old-MM TC.
  No comparison tolerance was relaxed to disguise the difference.

Final publication/run/browser verification is recorded below after deployment.
