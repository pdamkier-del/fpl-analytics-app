# Full model audit — 2026-10-12

Branch `model-audit-optimization-20261012`, reference commit `2b1983accd89163334053b38eff8543911bcc84f`. No production deployment, private manager-data publication, account operation or locked coefficient replacement. `locked_model_active=false`.

## Decision

No mathematical experiment yet qualifies for promotion. The supported fixes are forecast-content identity and consistent display of original MM/PM inputs. The minute sampler is an isolated experiment; finishing shrinkage fails cross-period validation. A shared starter-duration half-life candidate improves that component in two chronological checks, but has not passed full PM/TS validation. The original 2,125-point ledger remains unchanged, but does not demonstrate six-GW historical planning.

## Prioritized findings

| Priority | Finding | Evidence and candidate action |
|---|---|---|
| P0 | Historical replay silently truncates the TS horizon | Authoritative GW6–38 forecast contains 33 origin/target cells versus 183 required. Planner selects available GWs and truncates weights; gaps can compress weights. Add an explicit audit/guard; never manufacture historical future forecasts. |
| P0 | Cutoff alone does not identify a forecast | Browser cache and backend jobs accepted changed predictions at the same cutoff. Canonical whole-payload SHA-256 now binds request, result and cache, with before/after backend checks. Actual manager-state is preserved. |
| P1 | Conditional minute means are not preserved by PM | Clipped, rounded Normal(90,10) has mean 86.0122 minutes. Cameo support 1–45 conflicts with some means above 45. A mean-preserving sampler is tested in isolation, not promoted. |
| P1 | Player profile mixed experimental MM with original PM | vNext xMin/P(start) was shown beside original PM xP, although PM/TS did not use vNext. Primary fields now use original MM; the separate experiment remains linked. |
| P1 | Haaland starter duration overreacts to latest appearance | Locked half-life 0.321926 appearances gives the latest 79-minute game dominant weight over five 90-minute starts. No player-specific override or unvalidated parameter edit. |
| P1 | Historical source availability is conditional | kickoff+4h is a documented proxy, not verified publication/revision time. Full leakage-safe certification is blocked. |
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
2. Exact historical publication/revision clocks remain unknown. Historical roster gaps/conflicting mappings and 334 incomplete BPS rows are unresolved; no repeat of the same 223 source versions is presented as progress.
3. 2024/25 supports conditional component tests, not full independent model certification: historic prices/cohorts/future snapshots are incomplete, model training overlaps parts of 2024 and scoring differs by season. Older seasons lack a verified complete aligned MM/PM/TS bundle for this audit. Current 2026 future outcomes are not yet known.
4. Neither mathematical candidate passes the documented tests. No improved whole-season FPL score is claimed.
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

The duration improvement holds in these chronological component checks, making it the best mathematical research candidate so far. Missing 2025 playerstats are excluded, not converted to zero; its observed squad history differs from the full registered-roster MM ledger. Frozen training already overlaps 2024, publication clocks are proxies, and full vFinal / six-GW TS acceptance remains unavailable. It is therefore not enabled in production. Reproduce with `PYTHONPATH=src:scripts python scripts/audit_duration_walkforward.py`.

Browser audit of the published profiles confirmed Haaland GW7 5.92 xP / 68 min / 84%, Saka 5.74 xP / 85 min / 95%, both labelled MM vNext for minutes while xP remains Original PM. Profile source mixing is observable, not only inferred from code. Candidate primary-profile rendering is exercised against an explicit synthetic transport fixture. No private team was used.

## Joint start-count weakness

The live 120 team/fixture distributions have mean probability 0.2591 of exactly 11 independently sampled starters, and 0.3724 of more than 11, despite marginal P(start) summing to 11 within 1.2e-12. A research candidate is a conditional joint distribution P(z) proportional to exp(sum_i a_i z_i), restricted to sum_i z_i=11 and legal role assignments. The a_i would be calibrated to preserve the intended marginal probabilities, rather than simply renormalizing an independent draw. This would require an original-input historical point backtest; no such sampler is promoted or substituted here.
