# Full model audit — 2026-10-12

Branch `model-audit-optimization-20261012`, reference commit `2b1983accd89163334053b38eff8543911bcc84f`. No production deployment, private manager-data publication, account operation or locked coefficient replacement. `locked_model_active=false`.

## Decision

No mathematical experiment yet qualifies for promotion. The supported fixes are forecast-content identity and consistent display of original MM/PM inputs. The minute sampler is an isolated experiment; finishing shrinkage fails cross-period validation. A shared starter-duration half-life candidate improves that component in two chronological checks, but has not passed full PM/TS validation. The original 2,125-point ledger remains unchanged, but does not demonstrate six-GW historical planning.

## Prioritized findings

| Priority | Finding | Evidence and candidate action |
|---|---|---|
| P0 | Historical replay silently truncates the TS horizon | Authoritative GW6–38 forecast contains 33 origin/target cells versus 183 required. Planner selects available GWs and truncates weights; gaps can compress weights. Add an explicit audit/guard and reject missing player-week rows in the live adapter; never manufacture historical future forecasts. |
| P0 | Cutoff alone does not identify a forecast | Browser cache and backend jobs accepted changed predictions at the same cutoff. Canonical whole-payload SHA-256 now binds request, result and cache, with before/after backend checks. Actual manager-state is preserved. |
| P1 | Conditional minute means are not preserved by PM | Clipped, rounded Normal(90,10) has mean 86.0122 minutes. Cameo support 1–45 conflicts with some means above 45. A mean-preserving sampler is tested in isolation, not promoted. |
| P1 | Player profile mixed experimental MM with original PM | vNext xMin/P(start) was shown beside original PM xP, although PM/TS did not use vNext. Primary fields now use original MM; the separate experiment remains linked. |
| P1 | Haaland starter duration overreacts to latest appearance | Locked half-life 0.321926 appearances gives the latest 79-minute game dominant weight over five 90-minute starts. No player-specific override or unvalidated parameter edit. |
| P1 | Historical source availability is conditional | The archived locked replay uses kickoff+3h; current live and new component tests use kickoff+4h. Neither is a verified publication/revision time. Full leakage-safe certification is blocked. |
| P2 | Realized simulation starts are not an exact XI | MM sums P(start) to 11 but PM samples independent starts. Structural weakness; accuracy impact not established. No new XI rules introduced. |

## Focus players and mathematical trace

Haaland is FPL ID 411: six verified starts, 529 minutes. GW7 original P(start)=83.823%, conditional starter duration=80.277, unconditional MM xMin=68.302. The original composition is p_start × starter_mean + (1−p_start) × q_sub × cameo_mean. Six historical starts do not mathematically require future P(start)=100%. The remaining start reduction comes from the shared MM, not an explicit Haaland override.

Saka is FPL ID 12, not 17: six starts, 506 minutes. His xP is driven by playing time, normalized goal/assist allocation and event-based bonus. No unexplained player multiplier or confirmed penalty double counting was found: explicit penalty goals are removed from ordinary goal intensity before penalty events. Penalty miss points are a subset of negative points, never an additional additive component.

Chelsea has 15 official team goals versus 8.51 provider xG in six matches. Team scores include own goals; player-goal sums are not the same target. A general shrinkage candidate uses theta ~ Gamma(tau,tau), G|theta ~ Poisson(theta X), so E[theta|G,X]=(G+tau)/(X+tau), and lambda_new=lambda_original × E[theta|G,X]. Tau is prior exposure in expected goals, shared across teams. This is a testable candidate, not a Chelsea-specific correction.

The sampler candidate inverts the exact expectation of a rounded, clipped Normal: E[Y]=1+sum(k=1..89) Phi((location−k−0.5)/sigma), choosing location so E[Y] equals the supplied conditional mean. Original sigma=10/7 and model inputs remain fixed. Physical 1–90 support admits early substitutions; boundary means consume the same random draw count. Changed event paths mean individual fixed-seed xP differences are not proof of improved accuracy.

## Backtests and acceptance

The archived integrated PM GW22–38 cohort has 11,794 rows / 144 fixtures. Its original minute inputs are not relabelled as the latest locked MM benchmark. Fixed-seed, paired 400-draw replay:

| Metric | Original | Mean-preserving candidate |
|---|---:|---:|
| FPL point MAE | 0.919069 | 0.919422 |
| FPL point RMSE | 1.846165 | 1.849904 |
| MAE GW22–30 | 0.927744 | 0.927848 |
| MAE GW31–38 | 0.908538 | 0.909193 |

Paired MAE delta +0.000353; fixture-block bootstrap 95% CI [−0.002356, +0.003051]. No documented improvement. This period was already reused during model development; another split does not create an independent holdout.

Finishing tests cover 380 matches / 760 sides per season, 660 forecast sides from GW6 onward. The transparent xG proxy uses only history whose kickoff+4h timestamp is strictly before the recorded origin deadline, including postponed games by timestamp. It is not a comparison against frozen PM or full TS. Tau=20 was selected on 2024/25 GW6–21 by Poisson deviance then MAE:

| Period | Baseline goal MAE | Selected tau=20 MAE | Paired delta 95% CI |
|---|---:|---:|---|
| 2024/25 GW22–38 | 0.915610 | 0.925872 | [−0.002295, +0.022772] |
| 2025/26 GW6–38 | 0.899893 | 0.899235 | [−0.009801, +0.008911] |

The selected method worsens the first later period and lacks a robust improvement on the following season. Reject promotion. 2024 xG is reconstructed from historical player observations, not assumed to be the same provider as 2025. The 2025 period has been used in earlier development, so it is not a pristine independent whole-model holdout. An earlier single-season tau=50 proxy result is exploratory, not an acceptance test.

## Locked baseline / source integrity

Current original cutoff: `2026-10-12T10:45:27.093744+00:00`, workflow https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38238230716. Checksummed source restore gives 3,775 training rows GW1–6, 60 future fixtures and 4,002 player-fixture forecasts GW7–12. A fresh original inference reproduced all watched outputs/components exactly (maximum absolute delta 0.0); saved forecasts were not substituted into fresh inference. Fixture/player identities are unique and historical availability is before cutoff.

Authoritative 2,125 artifact: workflow https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/37612845586, artifact 11480605718. Downloaded ZIP SHA-256 verified as `78127ec480c119d95a60fabab7d3575e7690f304defef1b365831204f6e5cea6`. Ledger accounting preserves 2,125 points, 44 transfers and 28 hit points. Its 33 decision origins each contain only that decision's GW: 150 required future horizon cells are missing. Archived locked MM has 26,159 rows: start Brier 0.069635, log loss 0.227819, minute MAE 10.5331 / RMSE 20.4945. These audit metrics do not establish a new model improvement.

Original MM feeds original PM/vFinal and TS v3. Medical-return MM vNext is separate; matching cutoff does not make its forecasts the minute source of PM. Workload, restitution, medical boundary, role competition, goal/assist allocation, keeper events, on-pitch clean sheets and event-based BPS remain the original implementations. TS weights/search, official hits, purchase-price selling logic and uncertainty buffer are unchanged. No alternative chip policy is introduced.

## Reproduction

Python 3.12, pinned `requirements-model-checkpoint.txt`, `requirements-model-tests.txt`, plus requests. From repository root:

```sh
python scripts/current_diagnostic_checkpoint.py restore
python scripts/restore_2024_25_data_checkpoint.py
PYTHONPATH=src:scripts python -m pytest tests -q
node tests/test_classic_manager.js
PYTHONPATH=src:scripts python scripts/locked_numerical_runtime.py scripts/audit_full_model_chain.py --simulate
PYTHONPATH=src:scripts python scripts/locked_numerical_runtime.py scripts/audit_historical_sampler.py
python scripts/audit_finishing_cutoff_walkforward.py
```

Download the pinned benchmark artifact above into `analysis/results/full-model-audit-20261012/locked-2125`, then run `scripts/audit_locked_historical_horizon.py`. The isolated `full-model-audit.yml` workflow runs these steps with read-only permissions, uploads public diagnostics and never publishes Pages or private manager results.

## Remaining blockers and readiness

1. Complete historical future fixture/roster/price snapshots at each origin deadline are needed for a faithful full six-GW TS candidate replay. Final realized schedules or later-deadline predictions introduce hindsight. The 2,125 baseline cannot be silently rebuilt with different information and called unchanged.
2. Exact historical publication/revision clocks remain unknown. Historical roster gaps/conflicting mappings and the original 334 incomplete BPS rows are unresolved; the restored current cutoff actually quarantines 617 rows in total (1,204 verified), including 283 additional rows; no repeat of the same 223 source versions is presented as progress.
3. 2024/25 supports conditional component tests, not full independent model certification: historic prices/cohorts/future snapshots are incomplete, model training overlaps parts of 2024 and scoring differs by season. The checksum-verified Core also contains 2022/23 and 2023/24 observations, but older seasons lack verified official-deadline and complete aligned MM/PM/TS future-snapshot bundles for this audit. Current 2026 future outcomes are not yet known.
4. No mathematical candidate has passed full PM/TS acceptance. The duration component improves its conditional-minute tests. No improved whole-season FPL score is claimed.
5. Forecast-ID adoption requires coordinated backend, frontend and publisher rollout. Old unsealed snapshots/plans require refresh. This proposal remains on the separate branch.

Verdict: diagnostic use with explicit freshness/state gates only; not certified live, no mathematical promotion. `locked_model_active=false` remains unchanged.

## Full focus tables

| Player / GW | Original simulated minutes | Shadow minutes | Original xP | Shadow xP |
|---|---:|---:|---:|---:|
| Haaland / 7 | 68.547 | 69.555 | 5.920 | 5.650 |
| Haaland / 8 | 66.677 | 68.353 | 4.622 | 4.907 |
| Haaland / 9 | 69.093 | 66.438 | 5.332 | 5.322 |
| Haaland / 10 | 67.638 | 70.170 | 4.455 | 4.575 |
| Haaland / 11 | 67.575 | 69.388 | 5.300 | 5.428 |
| Haaland / 12 | 70.293 | 70.675 | 3.695 | 3.565 |
| Saka / 7 | 82.828 | 83.250 | 5.740 | 5.610 |
| Saka / 8 | 80.222 | 85.703 | 6.237 | 6.817 |
| Saka / 9 | 80.522 | 85.030 | 4.947 | 5.510 |
| Saka / 10 | 81.860 | 85.022 | 6.610 | 7.435 |
| Saka / 11 | 80.975 | 84.720 | 6.423 | 7.060 |
| Saka / 12 | 81.912 | 85.070 | 6.207 | 6.205 |

| Saka GW | xP | Appearance | Goals | Assists | CS | DefCon | Negative | Bonus |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 5.740 | 1.952 | 2.038 | 0.690 | 0.325 | 0.170 | -0.207 | 0.772 |
| 8 | 6.237 | 1.903 | 2.500 | 0.735 | 0.340 | 0.185 | -0.220 | 0.795 |
| 9 | 4.947 | 1.910 | 1.650 | 0.472 | 0.390 | 0.150 | -0.220 | 0.595 |
| 10 | 6.610 | 1.927 | 2.575 | 0.772 | 0.482 | 0.155 | -0.200 | 0.897 |
| 11 | 6.423 | 1.915 | 2.575 | 0.743 | 0.380 | 0.155 | -0.158 | 0.812 |
| 12 | 6.207 | 1.930 | 2.462 | 0.698 | 0.340 | 0.175 | -0.152 | 0.755 |

| Chelsea GW | Original goal intensity | Illustrative tau=50 intensity |
|---|---:|---:|
| 7 | 1.3429 | 1.4918 |
| 8 | 1.4181 | 1.5754 |
| 9 | 1.5272 | 1.6967 |
| 10 | 1.3175 | 1.4636 |
| 11 | 1.3914 | 1.5458 |
| 12 | 1.2832 | 1.4256 |

Tau=50 is illustrative, not the selected cross-season candidate. At the selected tau=20 the current Chelsea posterior factor would be 35/28.51; its deployment is rejected.

## Shared starter-duration candidate

A third experiment changes only the shared duration half-life on covered histories. The original half-life formula is evaluated unchanged at 0.321926; the candidate value 3.0 is selected from the 2024/25 GW6–21 development slice. No player ID enters fitting. This is a conditional-duration experiment, not an exact re-run of full locked MM with its complete registered-player ledger.

| Later period | Reference half-life duration MAE | Candidate half-life=3 MAE | Paired delta 95% CI |
|---|---:|---:|---|
| 2024-25_GW22-38 | 8.303487 | 7.619870 | [-0.9390922387086343, -0.4366331184636552] |
| 2025-26_GW6-38 | 8.042755 | 7.635071 | [-0.5680212152044046, -0.25575968621767203] |

| Current GW7 player | Original conditional minutes | Candidate conditional minutes | Original xMin | Component-only xMin with P(start) fixed |
|---|---:|---:|---:|---:|
| Haaland | 80.277 | 86.974 | 68.302 | 73.915 |
| Saka | 88.972 | 85.687 | 85.255 | 82.119 |

The duration improvement holds in these chronological component checks, making it the best mathematical research candidate so far. Missing 2025 playerstats are excluded, not converted to zero; its observed squad history differs from the full registered-roster MM ledger. Frozen training already overlaps 2024, publication clocks are proxies, and full historical vFinal / six-GW TS acceptance remains unavailable. It is therefore not enabled in production. Reproduce with `PYTHONPATH=src:scripts python scripts/audit_duration_walkforward.py`.

Browser audit of the published profiles confirmed Haaland GW7 5.92 xP / 68 min / 84%, Saka 5.74 xP / 85 min / 95%, both labelled MM vNext for minutes while xP remains Original PM. Profile source mixing is observable, not only inferred from code. Candidate primary-profile rendering is exercised against an explicit synthetic transport fixture. No private team was used.

## Joint start-count weakness

The live 120 team/fixture distributions have mean probability 0.2591 of exactly 11 independently sampled starters, and 0.3724 of more than 11, despite marginal P(start) summing to 11 within 1.2e-12. A research candidate is a conditional joint distribution P(z) proportional to exp(sum_i a_i z_i), restricted to sum_i z_i=11 and legal role assignments. The a_i would be calibrated to preserve the intended marginal probabilities, rather than simply renormalizing an independent draw. This would require an original-input historical point backtest; no such sampler is promoted or substituted here.

## Duration candidate propagated through original PM

All 4,002 forecasts were rebuilt through the original `build_fixture_components` and `assemble` functions. This recomputes goal/assist allocation, nonlinear DefCon calibration, discipline and own-goal probability from new expected exposure. Penalty/BPS rate90 inputs have unchanged role/history covariates. No simplified PM is introduced. Rebuilding original components differs only by CSV-level floating-point rounding (maximum 3.6e-15); original 400-draw point outputs reproduce exactly before applying the candidate.

| Player / GW | Original MM xMin (GW7) | Original simulated xMin | Candidate simulated xMin | Original xP | Candidate xP |
|---|---:|---:|---:|---:|---:|
| Haaland / 7 | 68.302 | 68.547 | 70.945 | 5.920 | 5.857 |
| Haaland / 8 | — | 66.677 | 72.865 | 4.622 | 5.522 |
| Haaland / 9 | — | 69.093 | 70.845 | 5.332 | 5.277 |
| Haaland / 10 | — | 67.638 | 72.582 | 4.455 | 4.537 |
| Haaland / 11 | — | 67.575 | 74.185 | 5.300 | 5.190 |
| Haaland / 12 | — | 70.293 | 71.280 | 3.695 | 3.510 |
| Saka / 7 | 85.255 | 82.828 | 78.705 | 5.740 | 5.447 |
| Saka / 8 | — | 80.222 | 79.332 | 6.237 | 6.457 |
| Saka / 9 | — | 80.522 | 77.103 | 4.947 | 4.777 |
| Saka / 10 | — | 81.860 | 78.650 | 6.610 | 6.575 |
| Saka / 11 | — | 80.975 | 79.403 | 6.423 | 6.513 |
| Saka / 12 | — | 81.912 | 81.052 | 6.207 | 6.200 |

The original PM sampler is deliberately retained in this experiment, so its clipping bias remains. MM expected minutes and finite-draw simulated minutes are distinct quantities. Current goal outcomes are unknown; these before/after values do not measure accuracy.

Eight independent 400-draw seeds were also tested on the complete two GW7 fixture rosters. Their paired Monte Carlo intervals quantify simulation precision, not predictive uncertainty or historical accuracy:

| Player | Original mean xP | Candidate mean xP | Paired xP delta | Monte Carlo 95% CI |
|---|---:|---:|---:|---|
| Haaland | 5.6816 | 5.9569 | +0.2753 | [-0.12958076000925434, 0.6802057600092545] |
| Saka | 5.5722 | 5.5237 | -0.0484 | [-0.29399339227860605, 0.19711839227860556] |

Both point-delta intervals include zero. The stronger evidence remains the earlier conditional-minute accuracy improvement; full historical PM/TS acceptance is still required. Reproduce with `audit_duration_pm_shadow.py` and then `audit_duration_pm_precision.py` under `locked_numerical_runtime.py`.

Current source-quality correction: 617 BPS player-match rows are quarantined, not just the older 334 investigated rows. Required missing-field counts are chances_created 113, dispossessed 118, was_fouled 292, accurate_passes_percent 18 and tackles_won 284 (overlapping row counts). Only 1,204 rows are verified. No unavailable field is imputed as zero. This is an additional concrete certification blocker.

## Regular-starter calibration and older-season inventory

The original archived MM was also checked on 2,629 targets with six prior observed appearances all started, using only outcomes whose recorded proxy clock is strictly before the target cutoff. Predicted start rate is 87.71%; observed is 87.14%. For forwards alone (219 targets), predicted is 85.21%, observed 85.39%. Predicted mean minutes over the whole regular-starter cohort are 77.63 versus 76.09 actual. Thus the evidence does not support forcing P(start)=100% after six starts, or claiming a universal low-minute bias. The starter-duration result is a distinct conditional component improvement. These reused historical diagnostics do not establish calibration for an individual future fixture.

The original Core was restored read-only and SHA-256 verified: `a4742428fb0c9943ff3ee565f765eb98d733a1690180c566d6df794786ef409f`. It contains 26,505 observations in 2022/23, 29,725 in 2023/24, 27,283 in 2024/25 and 29,747 in 2025/26. All carry a September 2026 retrospective capture timestamp; this is not the original publication clock. An event number in `fixture_schedule_snapshots` is not an official deadline timestamp, and final schedules captured after the season cannot be treated as origin-known future schedules. Older observations are present; verified complete older-season deadline/future-snapshot bundles are the missing pieces. No deadline is guessed from kickoff to create a claimed leakage-safe FPL backtest.

Reproduce with `python scripts/restore_core_checkpoint.py --out work/core.sqlite3` and `PYTHONPATH=src:scripts python scripts/audit_regular_starter_calibration.py` after the pinned benchmark artifact has been restored. Tests explicitly exclude delayed prior-GW outcomes and targets already known at cutoff.

Validation at commit `7c5fce6`: 464 local regression tests, client/profile/deadline JavaScript tests, and successful complete isolated CI https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38299089926, including original-PM propagation and repeated-seed tests. Additional calibration tests are included in the next commit. GitHub comparison against the frozen base confirms no existing `src/` model file and no `model/` checkpoint/parameter file has changed.


## Further confirmed scoring and catalogue findings

**P1: own goals do not update the shared scoreline.** The locked simulator samples own goals after calculating goals conceded and clean sheets. A controlled forensic fixture produces own_goals=1, goals_conceded=0, clean_sheet=1 for its own-goal scorer. This is an internal scoring contradiction, not a source-data assumption. The existing baseline is preserved and the test explicitly documents the defect. A correction must put each own goal on the opposing team's goal timeline during the scorer's on-pitch interval, update conceded goals / clean sheets and recalculate known BPS/bonus consistently. The scope of the team goal intensity must be checked to avoid adding an event already counted in a total-goal mean. No correction is silently installed in the locked simulator.

**P1: stale market data could pass a valid GW/cutoff check.** Planning previously checked the official GW/deadline but not current official prices, clubs or positions. The candidate browser gate and backend now require a matching official catalogue, before/after backend calculation; a changed price, club, position or roster requires a fresh forecast, without repricing the locked model in JavaScript or deleting actual manager-state. All 667 cutoff-matched current players passed the new backend catalogue check. Same-GW changed-price/identity cases are covered by tests.

Saka's GW7 goal component is now traced further: 1.7875 ordinary-goal points plus 0.25 penalty-goal points = 2.0375, within total 5.74 xP. Haaland has 2.98 ordinary-goal points and 0.07 penalty-goal points within 5.92 xP. This instrumentation reproduces the saved point outputs exactly. Penalties are not the main contributor to Saka's GW7 total.

A likely early-season weakness is the penalty-taker fallback: Haaland's roster-normalized weight is 0.1474, versus Saka's 0.9097. The original model learns current-season attempts and otherwise falls back to goal-rate weights; these are not verified primary-taker probabilities. Historical role priors could be a general research candidate, but no manual Haaland assignment is inserted. Ordinary scoring weights also retain inclusive goal/xG rates; the penalty redistribution needs explicit non-penalty data and calibration before claiming a player-level fix.

Discipline has a possible exposure inconsistency: a probability derived from 45 expected minutes is then applied only if the player appears. With P(play)=0.5 and yellow hazard=0.2/90, the input probability 0.09516 becomes unconditional simulator probability 0.04758. This requires a conditional-hazard backtest; it is not declared a proved point-accuracy improvement.

## Active-player metrics and historical source reconstruction

The mean-preserving sampler improves minute MAE in the reused archived PM cohort, 11.8432→11.4832, while total point MAE slightly worsens. Crucially, all-row point MAE 0.9191 includes many inactive-player zeroes: among the 4,350 played rows it is 2.0135→2.0189, and among 3,168 actual starts 2.3369→2.3404. These are subgroup diagnostics, not training selection or independent promotion evidence. Detailed position metrics are retained in sampler_subgroup_report.json.

The frozen Core has no duplicate or missing started/minutes records among its 29,747 2025/26 observations. All 26,159 archived locked conditional starter durations were independently reconstructed from strict pre-cutoff history and the original half-life; maximum rounding difference was 5.7e-14. This supports historical duration propagation without guessed histories.

A further point-replay smoke test exposed a provenance issue: the 2,125 workflow regenerates GW1–38 base/role/workload/FA features and temporarily overwrites cached input paths. Those exact fresh feature files are not included in its uploaded prediction artifact. Replaying its first fixture using the repository's cached feature files matched 72 identities but differed by up to 0.7025 xP. This is not evidence that a mathematical candidate improves the baseline. Its original-source recipe was therefore being reconstructed in a separate detached checkout of 952b809, preserving the audit branch and immutable benchmark.

The original min-GW1 P(start) and full role/workload generation completed, but the local execution environment disconnected before the warmed-input point smoke or full candidate replay could complete. No historical whole-chain candidate point total is claimed. This continuation is explicitly blocked locally, not marked as a completed exact reproduction of 2,125.

## Latest checkpoint

The latest locally completed suite before the environment disconnected had **468 passing tests**, plus the classic-manager, profile and forecast-window JavaScript checks. The 667-player catalogue check, exact current 4,002-row forecast reconstruction and event decomposition also passed. Public source/results were saved on the separate audit branch; no private manager-state, purchases or tokens were included.

Complete expanded CI at a4e7e0: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38300513270. The next commit adds the tested catalogue/event audits and their cloud reproduction. Production stays unchanged and locked_model_active=false.
