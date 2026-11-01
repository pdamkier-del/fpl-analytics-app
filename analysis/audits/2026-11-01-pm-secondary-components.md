# Secondary PM-component audit — 1 November 2026

**Scope:** Independent read-only code review of `joint_simulator.py`, `point_accounting.py`, `bps.py`, `defcon.py` and existing precision audit. Base branch `audit-systematic-precision-20261101`; this document does **not** change model logic, locks, production or previews. No new empirical component-calibration replay was run for this report.

## What the existing evidence does and does not show
- Prior 341-match / 27,092-row audit provided event calibration for goals, assists and clean sheets, but **not an independently demonstrated position-specific forecast-versus-actual calibration for GK saves, save-point buckets, defender DC-point hit rates, bonus probabilities or BPS residuals**. Do not infer that passing 1,111 regression tests establishes those calibrations.
- Existing point-accounting code correctly prevents double-counting `penalty_miss_pts` as a second deduction; a keeper penalty save is deliberately present both in `saves` and `penalty_saves`, awarding regular save-bucket credit and the distinct penalty-save points. Avoid reporting that as an error without checking the FPL rules.
- BPS is a season-specific deterministic known-event function plus fitted residual background because full event data are unavailable. A fitted residual may conceal systematic role/position miscalibration, especially after an input/minutes distribution change.

## Priority 1: goalkeeper saves / penalty save interaction

`joint_simulator.py:296-305` sets

```
E[regular saves | simulated minutes m] = max(0, lambda_saves - lambda_opp_pen * (1-team_pen_conv) * p_pen_save_given_miss) * m/90
```

and adds the **separately sampled** opponent penalty saves to `r.saves`. This is an intention to prevent double counting, but the subtraction uses team-level expected conversion, whereas penalty events use the sampled taker conversion and the actually on-pitch keeper. Moreover, `lambda_saves` semantics and whether it includes penalties need source-level verification.

**Conditional-coverage consideration:** If a goalkeeper has only a fraction of 90-minutes coverage, the regular-saves component scales by m/90; actual penalty-save events are timed and attributed to who is on the pitch. This can be consistent under uniform event times. But if opponent penalty conversion is changed conditionally, the subtraction and actual event model must be evaluated using exactly the same conversion process. `hc/ac` may be replaced by `conditional_penalty_conversion`, which deserves an explicit conservation test.

Required tests:
1. Input `lambda_saves=0`, positive penalty attempts and keeper save-on-miss probability, stable and switching goalkeepers: examine expected total saves and whether accounting is plausible.
2. For constant 90-min starter / varied individual taker-conversion, compare empirical save means from 10k+ draws to the intended `lambda_saves` definition.
3. Evaluate P(saves≥3,≥6,≥9), save points, PK save points, and component xP errors, by GK and opponent strength; report finite-N uncertainty.
4. Calibrate `save_bucket_tilts` over genuinely future/untouched labels rather than simply matching pooled save means.

## Priority 2: defensive contributions (DC)

`joint_simulator.py:306-307` uses `NB2(dc_mu_90 * m/90, dc_alpha)`, then season-specific `dc_points_from_count`. `defcon.py` uses threshold 10 for DEF and 12 for MID/FWD (2 points; GK excluded). Thresholds and component points are encoded, but **a correct threshold does not prove calibration near the threshold**.

The model scales DC count with simulated minutes but assumes a fixed per-minute count rate conditional on participation; substitutions, role shifts and score-state could change this. Verify against actual FPL DC point-award outcomes, not only available third-party defensive action counts. Report empirical and simulated hit rates by position, xM bucket, role and club, including uncertainty; special care for exactly 10/12 and near-threshold rows. Check 2024/25 scoring differences (DC=0) separately.

## Priority 3: clean-sheet probability and defensive conceded-goal points

`joint_simulator.py:287-294` derives conceded goals from the shared scoring event timeline and awards CS only for `minutes>=60` with no goal conceded **while on pitch**. The source-level event semantics are now coherent with the integrated own-goal repair; however minutes and actual goal times both drive CS calibration. The prior oracle analysis found large changes in CS-Brier when **actual team goals** were supplied, which partly removes irreducible match variance. This does not demonstrate a need to lower team goal lambda.

Required: player-level P(FPL CS award) reliability, Brier and log loss by GK/DEF/MID, pregame P(60+), team-lambda deciles and actual/substituted minutes. Compare team clean-sheet probability separately from player-specific CS; account for players subbed off before a late goal. Do **not** treat a team clean sheet and a player's FPL CS as the same outcome.

Goals-conceded points use `-(gc//2)` for GK/DEF, including only conceded while on pitch. Confirm against official FPL event labels at substitution boundaries and own goals.

## Priority 4: bonus/BPS

`bps.py` contains three season-specific known-event calculators and tie distribution; `joint_simulator.py:312-341` samples `bps_background_rate90` plus role-dependent variance after allocating the known events. Important: **bonus is joint/relative within a fixture**, so judging each player's BPS residual independently does not validate bonus probabilities.

Report event-conditioned BPS residual bias by position, minutes and team score; position-level P(1,2,3 bonus) reliability, rank/tie frequency and bonus-point xP MAE/bias. Check whether residual variance is too small after a brace, clean-sheet or red card. Validate 2026/27 rules only against 2026/27 labels, not the 2024/25 or 2025/26 season scoring environments.

## Test specification and acceptance

1. Frozen-cutoff join of forecast per-component expectations and actual FPL labels for CS, saves, save points, DC award, bonus points, goals conceded and negative events. If direct labels are absent, mark **NOT AVAILABLE**; never infer from goals or aggregate total points.
2. For each component: MAE/bias, Brier/log-loss for binary awards, reliability bins with sample counts, clustered intervals (fixture + player/GW dependence as relevant), by GK/DEF/MID/FWD and source availability.
3. Monte Carlo noise: compare 400/2k/10k and keep model comparison on common draws where possible; do not propose component recalibration on 400-draw noise.
4. Issue only a narrow candidate for components showing robust, repeatable miscalibration; demand prospective confirmation. Preserve original production, TSv3, baseline, and the separate Codex MM/assist branch.

**Current conclusion:** This inspection identifies **four targeted validation needs**, not four newly proven scoring-rule defects. The strongest new code-level sensitivity to test is potential mismatch of separately sampled penalty saves against the regular-save expectation subtraction. No justified PM parameter change yet.
