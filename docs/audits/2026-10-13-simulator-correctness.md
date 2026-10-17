# Opt-in simulator corrections — 13 October 2026

Requested in PR #3: https://github.com/pdamkier-del/fpl-analytics-app/pull/3#issuecomment-6140806893. Nothing is merged or deployed. Production joint_simulator.py, all fitted parameters and original MM/PM/TS/chip strategies remain unchanged. locked_model_active=false.

## Implemented correctness changes

Own goals are explicit opponent scoreline events, timestamped inside the committing player's half-open interval, with no normal scorer or assist. Their negative/BPS debit stays on the committer; overlapping players' conceded goals, clean sheets, points and known BPS reconcile against the same events. The ordinary goal intensity subtracts conditional own-goal mass and the time-integrated existing active-taker scored-penalty expectation from the original total team intensity. Explicit components exceeding that budget are rejected, never silently added on top or hidden by clipping.

The XI sampler requires exactly one goalkeeper and ten outfield starters. It projects infeasible marginal sums using a common logit shift within goalkeeper/outfield partitions; hard zero/one probabilities remain fixed, zero starter-minute caps cannot start, and unavailable p_start=q=0 players cannot appear. Feasible marginal vectors remain unchanged. Dependent rounding preserves each feasible marginal in expectation and exact cardinality in every draw. FPL fantasy-manager formation minima are not imposed on real clubs: a false nine does not force the lone FPL-labelled striker to start.

Bench appearances use vacant goalkeeper/outfield slots, at most five normal substitutes and three in-play windows, with half-time exempt. Closest windows can move later to avoid occupied slots. Conditional Normal minute distributions and their original supports are retained before feasibility caps; rejected/capped cameos are measured, not claimed to preserve their original marginals. This guarantees starting-XI cardinality and no slot/GK overlap, not a fully validated continuous 990-team-minute match model. Tactical transitions, concussion/medical/red-card departure timing and missing availability labels are not invented. Official normal-substitution reference: https://www.premierleague.com/en/news/2669074 ; separate concussion protocol: https://www.premierleague.com/en/news/4079828 .

## Regression and immutable benchmark

489 tests passed locally and in the final GitHub Actions run, including 5,000 XI draws/calibration, hard caps, false nine, slot/window limits, own-goal clean-sheet denial, conceded points, substitute/penalty overlap, total-mean conservation, invalid probabilities, exception-safe restoration, all three BPS seasons' draw-for-draw equivalence with corrections disabled, and the upper-bound floating timestamp regression.

Atomic captures now fsync, verify complete gzip/JSON and replace their final path only after validation. Corrupt input is detected before simulation; per-fixture checkpoints are bound to source records, seeds, evaluator/model hashes and numerical runtime. A truncated local 2024 capture contained 314 intact records. Regenerating GW37–38 from unchanged source recovered the missing tail; all four overlapping records matched exactly and the repaired file contained 330 verified records. No values were filled manually. Cache reuse on two real historical fixtures reproduced all numerical results.

Classic manager, profile and forecast-window JS tests passed. All 4,002 current baseline forecasts remain exact. All 26,159 historical reference xP/appearance/identity rows match the immutable archive; original TS still gives 2,125 points, 44 transfers and 28 hit points. Full unchanged PM→TS historical reproduction from archived MM inputs was verified in https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38361554492 . First corrective implementation/full regression/current/history run at 0b0a8fc: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38368218223 ; general audit: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38368218121 .

## Historical A/B scope and 2025 results

Fixed cutoff-generated inputs, current-GW origins 6–38, 330 fixtures/season, 400 draws and the original seeds. Actuals are joined to frozen Core fixture/player identities, never assumed zero. Own-goal-only, XI-only and both are distinct ablations. Original minute expectations are analytic; candidate minute expectations are simulated. This is reused model-development data, not pristine independent OOS; 2024 retains conditional role/news/BPS/penalty and kickoff+4h proxies, 2025 uses original kickoff+3h. Bootstrap intervals do not quantify all Monte Carlo uncertainty.

| 2025/26, 26,159 fixture rows | Point MAE | Point RMSE | Played-player point MAE |
| --- | ---: | ---: | ---: |
| Original | 0.929173 | 1.880707 | 2.034955 |
| Own-goal/budget correction | 0.924874 | 1.876748 | 2.026905 |
| Joint XI | 0.926301 | 1.879242 | 2.037471 |
| Both | 0.923335 | 1.878863 | 2.032506 |

Combined paired MAE delta -0.005838, fixture-block interval [-0.007667,-0.003946]; no rejected 2025 fixtures. Start Brier 0.069635→0.069497; point mean bias +0.019572→+0.004290. However played-player minute MAE worsens 20.6755→20.9084, and binned start ECE slightly worsens 0.008707→0.008979. Do not declare every component improved.

Marginal constraints can cause large changes on historical inconsistent inputs. In Chelsea–Liverpool GW7 (2025), Alisson has p_start=0 while Mamardashvili is 0.110637 and the other two keepers 0.006831 each. Requiring one keeper projects Mamardashvili to 0.734581, a +62.394 percentage-point change. This is a reported partition correction, not a player patch. It must be evaluated for calibration; no general claim of negligible marginal changes is made.

## Confirmed 2024 evaluation-adapter defect and corrective rerun

The first 2024 ablation rejected 35 fixtures in the own-goal/combined modes (70 fixture-mode failures): explicit components exceeded total intensity. Its partial 21,579-row result is not a whole-cohort accuracy win. The full XI-only comparison was slightly worse: MAE 0.975902→0.976249 and RMSE 1.924684→1.926479.

Inspection confirmed an exposure bug in the existing conditional adapter: penalty occurrence denominators and the league prior counted only matches with a positive penalty-event row. They measured attempts per penalty-match instead of per played match. The corrected adapter counts all known official fixture-side exposures and filters events by the same cutoff, including a regression for a postponed prior-GW game not yet played. It preserves the original occurrence/taker/conversion formulas, half-lives and selected coefficients. The 2025 immutable benchmark and production are not changed. Both original and candidate must be recomputed on the same corrected 2024 inputs before comparison. The original conditional penalty/role/BPS source caveats remain; the correction does not create certification.


## Final corrected two-season comparison (62374a7)

The final read-only A/B workflow completed successfully: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38375971604 . The separate full audit also passed: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38375971613 . All 489 Python regressions, current original forecast identity, JavaScript checks and the original TS accounting assertion passed. Both seasons cover all 330 fixtures, with zero rejected fixture-mode evaluations. The corrected 2024 comparison recomputes **both** sides on the same fixed exposure inputs; it must not be compared directly to the old pre-fix original score.

| 2024/25, 24,072 fixture rows | Point MAE | Point RMSE | Played-player minute MAE |
| --- | ---: | ---: | ---: |
| Original on corrected inputs | 0.991189 | 1.898567 | 22.105592 |
| Own-goal/budget correction | 0.989775 | 1.899470 | 22.105825 |
| Joint XI | 0.990948 | 1.901244 | 22.425458 |
| Both | 0.987544 | 1.899665 | 22.401269 |

Combined 2024 paired point MAE delta is -0.003645, fixture-block 95% interval [-0.005369,-0.001872]. Joint-XI-only and own-goal-only 2024 intervals include zero. Start Brier improves 0.085222→0.085137, but combined all-player point RMSE and played-player minute MAE worsen. In 2025, combined played-player point RMSE also worsens 2.924622→2.926763. Small aggregate MAE improvements on reused development periods therefore do **not** establish universal component improvement or independent acceptance.

The full final metrics for all four modes are committed as correctness_2024-25_ci_report.json and correctness_2025-26_ci_report.json, each recording evaluated commit and source run. The previous rejected 2024 report is retained under an explicit pre_exposure_fix filename. Correctness regressions are accepted as candidate evidence; model promotion remains withheld.

## GW7 focus, eight independent 400-draw seeds

Same audited cutoff 2026-10-12T10:45:27.093744+00:00. Seed averages are precision diagnostics, not the app's original single-seed output or new live recommendations.

| Quantity | Original | Both |
| --- | ---: | ---: |
| Haaland P(start) | 83.823042% | 83.815771% |
| Haaland simulated minutes | 66.876563 | 67.933750 |
| Haaland xP | 5.511563 | 5.547500 |
| Saka P(start) | 95.442210% | 95.443112% |
| Saka simulated minutes | 81.492813 | 81.449375 |
| Saka xP | 5.545000 | 5.580313 |
| Chelsea total goal intensity | 1.342868819888325 | 1.342868819888325 |

Haaland paired xP delta +0.035938, seed-variation interval [-0.220089,+0.291964]; Saka +0.035313, interval [-0.268376,+0.339001]. Both include zero. Neither start probability is forced to one; Haaland's frozen conditional-duration weakness is separate. Own-goal-only changes no minute distribution mathematically, but event draw ordering causes finite-seed variation.

## Acceptance

No production promotion or merge. Corrected 2024 comparison is complete with mixed precision outcomes; independent origin-safe publication/roster/price/schedule data and complete historical six-GW forecast cells still block whole-chain acceptance. The old 2,125 accounting replay is reproducible but its forecast horizon is incomplete; no candidate TS total is advertised as a true rolling six-GW improvement. Detailed public reports/artifacts contain no private manager-state or purchase prices.
