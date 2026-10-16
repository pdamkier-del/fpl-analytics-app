# Final individual MM integration — 2026-10-17

**PREVIEW READY – NOT YET CERTIFIED. No lock or production model activation.**

Draft PR #15. Preview: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/

## A. Architecture and verified reuse

PR #4 supplies historical individual MM identities/positions and role design; PR #8 supplies source caps, normal-role and existing return-duration protection. PR #9 supplies the selected B calibrator. PR #10/#12 supply error/cohort evidence; PR #11 supplies prior-only detailed roles and formation assignment. PR #13 supplies the fixed development-selected sigma30 PMF. PR #14 supplies the integration stop gates. None of these research PRs was merged into production.

`mm_candidate.py` is the shared preview contract/formation/PMF implementation. `mm_candidate_forecast.py` fits the original B calibrator using previous known labels only. `replay_mm_candidate_calibration.py` refitted this real inference entry point at every evaluation origin: **39,264 forecasts, maximum absolute difference 0** across p/q/s/c/x against PR #9. The bug caught during integration was temporary q-capping being carried across both projection passes; the final runtime correctly retains PR9's projected p and reuses the original upstream q on its final pass.

No PM, FPL scoring, TS or chips executed. All production `src`, `service`, `model` and frozen B inputs are checked unchanged against `56d637a` in CI. This branch stacks narrowly on #14; a future production change must selectively port reviewed dependencies rather than merge the whole research stack.

## B. Mathematics and contract

$$xM=p\,s+(1-p)\,q\,c.$$

p is marginal P(start), q is P(substitution on | no start), s and c are conditional mean durations. B uses the exact PR9 design, StandardScaler plus logistic regression C=0.1 (alpha10), then existing source/cap and exact 1GK+10 marginal projection. Training occurs chronologically using only known_at < cutoff. Hard valid OUT/SUSPENDED sources keep p=q=xM=0, even when historical outcomes contradict those sources. We do not invent expiry or clearance.

The formation selector retains PR11's last12-game formation mass (half-life5 observed games), 70-day role decay and Hungarian assignment score `logit(p) + .5*log(.02 + .78*exact_role_share + .20*role_family_share)`. It now **forbids** incompatible GK/outfield assignments and p=0 players, instead of merely assigning a soft 1e-4 penalty. It chooses the highest-frequency feasible historical formation, trying known alternatives only if needed. Fewer than3 prior complete XIs or no feasible assignment yields **Not Available**. Unknown detailed outfield roles stay unknown; a selected slot is a model assignment, not a newly verified primary role. Primary/secondary role probabilities are historical evidence; competing players share observed role support.

The XI is a deterministic constrained point choice, not a calibrated distribution over joint XIs or a claim to have identified the most probable joint XI. B's marginal start probabilities are never nudged. `FormationHistory`, `RoleHistory` and the existing classifier/template were audited; no second production role calculation was introduced. The selector intentionally preserves PR11's evaluated formation weights rather than silently adding FormationHistory's separate smoothing settings.

PR13 conditional duration shapes are bounded exponential-tilted Gaussian-shaped discrete masses, start0..90/cameo1..90, sigma30 selected only on 2024/25GW14–21. The mixture is `p*startPMF + (1-p)*q*cameoPMF + (1-p)*(1-q)*delta0`. Numerical endpoint/mean repair gives **max |E[PMF]−xM|=2.84e-14 minutes**, checked at absolute tolerance1e−6, no relative tolerance. Mixture masses at0 /1–15 /16–60 /61–90 sum to1. Exact support endpoints imply point masses, not artificial probability floors.

Version `individual-B-formation-pmf-preview.1`, contract `fpl.mm/1.0`. Each output contains identity/club/fixture/GW/cutoff/data-at, normal/position roles, selected formation/slot, p/q/s/c/xM, all91 minute masses, four bins, interval, availability, version and uncertainty status. Independent certification is false. Forecast cutoffs are historical information origins; they are not fabricated historical calculation-publication timestamps. Snapshot data-at denotes the cutoff-bound replay input, with actual history/news clocks preserved in source manifests. Outcomes in the public **historical replay** are explicitly evaluation labels; prospective targets reject outcome fields.

## C. Identical-cohort historical comparison

39,264 identical player-fixtures, all40 club-seasons. 2024/25GW22–38 and2025/26GW6–38. Six requested arms actually executed through the common output pipeline; added XI/PMF arms intentionally retain B p/q/s/c/xM exactly, so their point-minute metrics are equal by construction and verified against the generated contract.

| mode          |     n |       mae |      rmse |   start_brier |   start_logloss |      bias |   over60 |
|:--------------|------:|----------:|----------:|--------------:|----------------:|----------:|---------:|
| B             | 39264 | 10.408358 | 20.172026 |      0.068827 |        0.226125 | -0.282791 |     1278 |
| best_existing | 39264 | 10.521392 | 20.416725 |      0.070115 |        0.231354 | -0.377657 |     1362 |
| original      | 39264 | 11.240711 | 21.115962 |      0.073445 |        0.241262 | -0.082509 |     1559 |
| B_XI          | 39264 | 10.408358 | 20.172026 |      0.068827 |        0.226125 | -0.282791 |     1278 |
| B_PMF         | 39264 | 10.408358 | 20.172026 |      0.068827 |        0.226125 | -0.282791 |     1278 |
| combined      | 39264 | 10.408358 | 20.172026 |      0.068827 |        0.226125 | -0.282791 |     1278 |

Reused PR9 combined paired4-GW bootstrap: B−best MAE−0.113034 [−0.148345,−0.074534]; Brier−.0012885 [−.0016937,−.0008726]. Separate season intervals are recomputed here in `paired_intervals.json`. No formation-nudge model is promoted: its previous RMSE/Brier/>60-tail failures remain valid stop reasons.

### Error distribution and tail contribution

| mode          |   median |       p90 |       p95 |       p99 |   top5_error_share |   top10_error_share |
|:--------------|---------:|----------:|----------:|----------:|-------------------:|--------------------:|
| B             | 1.965745 | 34.839239 | 50.723173 | 77.990725 |           0.320598 |            0.522310 |
| best_existing | 1.956279 | 35.166250 | 51.269090 | 79.388834 |           0.322593 |            0.524000 |
| original      | 3.355414 | 36.096952 | 54.184923 | 80.664544 |           0.312406 |            0.509336 |
| B_XI          | 1.965745 | 34.839239 | 50.723173 | 77.990725 |           0.320598 |            0.522310 |
| B_PMF         | 1.965745 | 34.839239 | 50.723173 | 77.990725 |           0.320598 |            0.522310 |
| combined      | 1.965745 | 34.839239 | 50.723173 | 77.990725 |           0.320598 |            0.522310 |

Shares above are fractions, not percentages. Per-arm 0–5/5–15/15–30/30–60/>60 counts and error contributions are in `error_bands.csv`. Top100 concrete errors for original/best/B are retained with canonical IDs, actual/expected minutes, roles, source flags and cutoffs. There is no new causal explanation inferred from a bad outcome alone.

| group                     |     n |       mae |      rmse |      bias |   start_brier |   over60 |
|:--------------------------|------:|----------:|----------:|----------:|--------------:|---------:|
| reserve                   | 24213 |  5.270075 | 14.131942 | -0.574010 |      0.034234 |      411 |
| rotation_or_short_history | 10244 | 21.211478 | 29.011152 | -0.271500 |      0.147045 |      618 |
| regular                   |  4807 | 13.267955 | 22.893855 |  1.160028 |      0.076386 |      249 |
| limited_history           |  9943 |  1.851208 |  8.429731 | -0.338096 |      0.011648 |       65 |
| documented_return         |  1193 | 22.381624 | 30.221133 | -9.392490 |      0.152746 |       91 |
| OUT                       | 11803 |  0.074727 |  2.080397 | -0.074727 |      0.000508 |        6 |
| SUSPENDED                 |   194 |  1.103093 |  9.458537 | -1.103093 |      0.010309 |        2 |

`limited_history` is an overlapping diagnostic group using weighted pre-cutoff history_n<3; it is not relabelled as a new verified tactical role. Rotations are evaluated by proper probability scores and calibration bins, not by calling a single correctly calibrated 50% forecast wrong. Existing PR9 matched role/rest/return paired intervals remain applicable because p/x are unchanged; all source medical and scheduled return1–3 flags remain in the per-row outputs. Unknown injury/training information remains unknown.

### All40 club-seasons, descending new MAE

| season   | club           |   original |   best_existing |   combined |   B_gain_vs_original |
|:---------|:---------------|-----------:|----------------:|-----------:|---------------------:|
| 2024-25  | Man City       |  18.662599 |       16.754505 |  16.637559 |             2.025040 |
| 2024-25  | Ipswich        |  16.565036 |       15.022570 |  14.832278 |             1.732758 |
| 2024-25  | West Ham       |  16.375065 |       14.934611 |  14.710523 |             1.664542 |
| 2024-25  | Man Utd        |  16.254522 |       13.777052 |  13.418600 |             2.835922 |
| 2024-25  | Spurs          |  15.881535 |       13.406895 |  13.197377 |             2.684158 |
| 2024-25  | Leicester      |  14.094676 |       12.163543 |  12.263495 |             1.831181 |
| 2024-25  | Liverpool      |  13.541704 |       12.737472 |  12.116220 |             1.425484 |
| 2024-25  | Fulham         |  13.323590 |       12.641919 |  12.051264 |             1.272326 |
| 2024-25  | Southampton    |  13.114166 |       11.977146 |  11.965295 |             1.148871 |
| 2024-25  | Aston Villa    |  13.184429 |       12.147908 |  11.944117 |             1.240312 |
| 2024-25  | Arsenal        |  12.342517 |       11.170673 |  11.113791 |             1.228726 |
| 2024-25  | Everton        |  10.967306 |        9.412867 |   9.607178 |             1.360128 |
| 2024-25  | Chelsea        |  10.099283 |        9.415525 |   9.247330 |             0.851953 |
| 2024-25  | Newcastle      |  11.251159 |        9.244533 |   9.091421 |             2.159738 |
| 2024-25  | Nott'm Forest  |  10.411619 |        9.477088 |   8.979348 |             1.432272 |
| 2024-25  | Crystal Palace |  10.156660 |        9.253073 |   8.896174 |             1.260486 |
| 2024-25  | Brighton       |  11.225124 |        8.721459 |   8.675618 |             2.549506 |
| 2024-25  | Wolves         |   9.405251 |        8.117235 |   7.969228 |             1.436022 |
| 2024-25  | Bournemouth    |   9.356386 |        7.232870 |   6.990065 |             2.366320 |
| 2024-25  | Brentford      |   7.773873 |        7.024508 |   6.621588 |             1.152285 |
| 2025-26  | Chelsea        |  14.558161 |       14.012438 |  13.840616 |             0.717545 |
| 2025-26  | Fulham         |  13.531702 |       13.061602 |  12.935349 |             0.596353 |
| 2025-26  | Newcastle      |  12.310593 |       12.057975 |  12.235110 |             0.075483 |
| 2025-26  | Arsenal        |  12.365779 |       12.031301 |  11.800237 |             0.565542 |
| 2025-26  | Wolves         |  11.614022 |       11.459118 |  11.692884 |            -0.078862 |
| 2025-26  | Man City       |  11.859516 |       11.524087 |  11.643786 |             0.215730 |
| 2025-26  | Aston Villa    |  11.496859 |       11.225350 |  11.008769 |             0.488090 |
| 2025-26  | Nott'm Forest  |  11.014917 |       10.725617 |  10.790627 |             0.224289 |
| 2025-26  | Leeds          |  10.699890 |       10.459626 |  10.540812 |             0.159078 |
| 2025-26  | Spurs          |  10.596432 |       10.281848 |  10.263783 |             0.332648 |
| 2025-26  | Liverpool      |  10.791521 |       10.335087 |  10.014507 |             0.777014 |
| 2025-26  | West Ham       |  10.164374 |        9.910380 |  10.009776 |             0.154598 |
| 2025-26  | Burnley        |   9.932859 |        9.787110 |   9.800308 |             0.132552 |
| 2025-26  | Man Utd        |   9.772829 |        9.294692 |   9.176968 |             0.595861 |
| 2025-26  | Crystal Palace |   9.738146 |        9.377725 |   9.054665 |             0.683481 |
| 2025-26  | Brighton       |   9.241308 |        9.025065 |   9.003888 |             0.237419 |
| 2025-26  | Brentford      |   8.963289 |        8.721664 |   8.649272 |             0.314016 |
| 2025-26  | Everton        |   9.006689 |        8.471426 |   8.193659 |             0.813030 |
| 2025-26  | Bournemouth    |   7.478725 |        7.301599 |   7.246905 |             0.231820 |
| 2025-26  | Sunderland     |   7.754996 |        7.176161 |   7.026234 |             0.728762 |

B vs best still improves31/40 point estimates and worsens9. Unadjusted club harm intervals previously flagged Everton2024/25, Newcastle2025/26 and Wolves2025/26. Common-pipeline equality is not evidence that these risks disappeared. No per-club switches or named-player boosts were fitted.

## D. XI and positions

| mode          |   n |   average_correct |   exact11_pct |   atleast10_pct |
|:--------------|----:|------------------:|--------------:|----------------:|
| B             | 660 |          9.119697 |     13.787879 |       42.272727 |
| best_existing | 660 |          9.096970 |     12.121212 |       42.878788 |
| combined      | 660 |          9.148485 |     15.303030 |       43.939394 |
| original      | 660 |          9.068182 |     12.575758 |       41.666667 |

All compared XI observations are the same **660 2025/26 team-fixtures**. Original/best/B comparators are explicitly unconstrained raw top11 as in PR11, not claimed legal 1GK references. Combined hard-constrained assignments are stored in `xi_assignments.csv.gz`. Exact11 and >=10 match the previous15.303%/43.939% references; average correct9.148485 vs B9.119697. Equivalent detailed2024/25 classified role evidence is **Not Available**, so these XI rates are not reported for both seasons or all39,264 rows.

Formation agreement against the sufficient same-source post-match classified ledger: **68.485%**. This is source-relative formation agreement, not independently verified in-match tactical ground truth. Slot correctness is retained perfixture in `xi_comparison.csv`; the full11/10/9/… histogram is in `xi_hit_distribution.csv`. Truth labels never enter the pre-cutoff selector. Paired4-GW XI intervals are in the contrasts below; these small XI point gains are not automatically robust improvements.

| slot   |   predicted |   starter_hits |   exact_role_hits |   starter_accuracy |   exact_role_accuracy |
|:-------|------------:|---------------:|------------------:|-------------------:|----------------------:|
| CAM    |         423 |            348 |               219 |           0.822695 |              0.517730 |
| CB     |         127 |            107 |                78 |           0.842520 |              0.614173 |
| CM     |         127 |            112 |                58 |           0.881890 |              0.456693 |
| DM     |          21 |             15 |                 8 |           0.714286 |              0.380952 |
| GK     |         660 |            620 |               620 |           0.939394 |              0.939394 |
| LAM    |         493 |            377 |               237 |           0.764706 |              0.480730 |
| LB     |         533 |            437 |               370 |           0.819887 |              0.694184 |
| LCB    |         660 |            575 |               515 |           0.871212 |              0.780303 |
| LCM    |         254 |            211 |               120 |           0.830709 |              0.472441 |
| LDM    |         398 |            338 |               194 |           0.849246 |              0.487437 |
| LW     |         134 |            101 |                51 |           0.753731 |              0.380597 |
| LWB    |         127 |            108 |                86 |           0.850394 |              0.677165 |
| RAM    |         493 |            383 |               254 |           0.776876 |              0.515213 |
| RB     |         533 |            453 |               366 |           0.849906 |              0.686679 |
| RCB    |         660 |            565 |               486 |           0.856061 |              0.736364 |
| RCM    |         254 |            206 |               112 |           0.811024 |              0.440945 |
| RDM    |         398 |            329 |               193 |           0.826633 |              0.484925 |
| RW     |         134 |            103 |                51 |           0.768657 |              0.380597 |
| RWB    |         127 |            102 |                74 |           0.803150 |              0.582677 |
| ST     |         704 |            551 |               506 |           0.782670 |              0.718750 |

## E. Probabilistic validation — gate not passed

| role                      |     n |      crps |   logloss |       p0 |   observed0 |   central50_inside |   central80_inside |   central90_inside |   shortest50_inside |   shortest80_inside |   shortest90_inside |
|:--------------------------|------:|----------:|----------:|---------:|------------:|-------------------:|-------------------:|-------------------:|--------------------:|--------------------:|--------------------:|
| ALL                       | 39264 |  6.656090 |  1.562013 | 0.634261 |    0.613183 |           0.816677 |           0.905588 |           0.948452 |            0.792609 |            0.876706 |            0.919596 |
| regular                   |  4807 |  8.570005 |  2.216327 | 0.078243 |    0.074683 |           0.693988 |           0.798003 |           0.913668 |            0.748076 |            0.794882 |            0.832744 |
| reserve                   | 24213 |  3.353777 |  0.830668 | 0.878422 |    0.856606 |           0.909470 |           0.953537 |           0.970925 |            0.881716 |            0.930987 |            0.956139 |
| rotation_or_short_history | 10244 | 13.563423 |  2.983604 | 0.318068 |    0.290512 |           0.654920 |           0.842737 |           0.911656 |            0.602889 |            0.786802 |            0.873975 |

Full widths and nominal contained **model mass** for both interval methods are in `uncertainty_summary.csv`, separately perseason/role. Four-band probability calibration is in `minute_band_calibration.csv`.

Prior central80 coverage90.5588% is reproduced. Shortest contiguous intervals, defined only from the PMF and without outcome fitting, cover87.6706% and average15.5789 minutes wide, vs25.2131 central. This is closer to80%, **not** proof of calibrated80% intervals. Many players have a large atom at0, making deterministic equal-tail intervals necessarily conservative. For example, average shortest80 contained model mass92.3095%, not exactly80%; reporting nominal confidence alone would hide this discreteness.

The numerical exact-mean repair has CRPS delta **0.000005910** and minute-logloss delta **0.000937319** vs PR13. Paired4-GW intervals:

```json
{
  "delta_crps": {
    "mean": 5.9095465635155275e-06,
    "interval95": [
      5.021156821901525e-06,
      6.7719255468819185e-06
    ]
  },
  "delta_logloss": {
    "mean": 0.0009373187272357795,
    "interval95": [
      0.00025968680475595195,
      0.0017475637765923483
    ]
  },
  "shortest_minus_central_coverage80": {
    "mean": -0.028881418092909537,
    "interval95": [
      -0.03191629015603103,
      -0.025833488484336073
    ]
  },
  "xi_combined_minus_B_correct": {
    "mean": 0.02878787878787879,
    "interval95": [
      -0.004664491298527441,
      0.06212121212121212
    ]
  },
  "xi_combined_minus_B_exact11": {
    "mean": 0.015151515151515152,
    "interval95": [
      0.0030303030303030303,
      0.030677206229353465
    ]
  },
  "xi_combined_minus_B_atleast10": {
    "mean": 0.016666666666666666,
    "interval95": [
      0.0030303030303030303,
      0.03048780487804878
    ]
  }
}
```

Thus the requested “improve calibration without worse CRPS/logloss” promotion gate is **not passed**. We do not hide the small loss increase: correcting endpoint means removes some tiny artificial tail mass. The PMF and intervals stay a separate labelled experimental preview component. Minute logloss uses explicit1e−12 clipping; contradictory hard-zero outcomes still imply infinite theoretical logloss. Predicted zero fraction63.4261% vs observed61.3183% indicates excess predicted zeros overall; all35 source-hard-zero appearances remain in evaluation.

## F. Holdout audit, source and live integration gates

Available frozen evaluation seasons are exactly the already repeatedly researched2024/25 and2025/26 periods. Current-season GW1–6 data have been repeatedly used in earlier app/Haaland/Chelsea/JoãoPedro diagnostics and are not documented untouched evaluation data. No later completed, preregistered B period is available in this evidence set. **No independent holdout validation is claimed.** Historic outcome/role publication uses inherited kickoff+3/4h proxies, not verified actual publication timestamps. Complete cup/Europe workload, clinical/training clearance and fixture-scoped suspension expiry remain missing.

`mm_candidate_forecast.py` provides a separate prospective inference/immutable local preregistration interface. It requires PR8 upstream tuples plus the exact prior-only B feature contract and source clocks; it rejects current/future labels, unknown training clocks, overlapping target fixtures, late registration and overwrites. Model/code identities accompany each record. This is preparation for prospective collection, **not a claim that independent future forecasts have already been registered**. A CI artifact is not itself durable third-party timestamp certification.

The existing live inference script produces a different legacy/vNext feature matrix; it cannot safely be relabelled B. The current B adapter therefore fails closed and the preview shows **current forecast Not Available**. No oldGW7 or historicalGW38 snapshot is presented as current. No current PM/xP/TS outputs were fabricated or recomputed with an unapproved MM.

## G. App, deployment, activation and rollback

The separate `mm-preview/` app displays real historical replay snapshots, clubs/GWs, expected formation/XI and alternatives, role competition, p/q/s/c/xM, minute bins and experimental intervals, Pitch/List sorting and player detail. Compressed payload SHA256 is verified in-browser. Failures show retry and hide results. No manager-state/localStorage/cookie/token code is touched.

The CI workflow refits B, runs the full pipeline, focused regressions, immutable production/frozen-input checks and preserves public evidence. Publication reuses the latest successful production Pages artifact and overlays **only** `mm-preview/`; every other production file must remain byte-identical. It persists only this new public research path to the live branch, for later forecast builds. No production MM switch or model merge. Deployment/browsing evidence is recorded in the completion checkpoint after verification.

Activation is **not permitted yet**. Necessary next gates: independently/prospectively recorded evaluation; review the three club risks and35 source conflicts; probabilistic non-inferiority/calibration; a verified current-season PR8→B feature/provenance bridge; audited current role identity/formation coverage; downstream PM effects evaluated under fixed PM after MM approval. Keep `locked_model_active=false`. Do not change PM/TS weights or the2125 benchmark.

Rollback: remove/revert only the `app/mm-preview/` public-path commit and rerun normal Pages publication, or republish the recorded previous production artifact under the existing publication lock. Production model files require no rollback because they were not changed. Leave the immutable historical evidence/draft PR intact.

## Reproduction

```bash
python -m pip install -r requirements-model-checkpoint.txt -r requirements-model-tests.txt requests tabulate
PYTHONPATH=src:scripts OPENBLAS_NUM_THREADS=1 python scripts/replay_mm_candidate_calibration.py
PYTHONPATH=src:scripts OPENBLAS_NUM_THREADS=1 python scripts/build_mm_integration_preview.py
PYTHONPATH=src:scripts OPENBLAS_NUM_THREADS=1 python scripts/report_mm_integration_preview.py
PYTHONPATH=src:scripts python -m pytest -q tests/test_mm_candidate.py tests/test_individual_mm_refinement.py
```

All actual model inputs and output hashes are in `manifest.json`. Gzip container content, decoded arrays and numerical differences must be distinguished. The completion checkpoint records clean-CI reproduction rather than assuming it.
