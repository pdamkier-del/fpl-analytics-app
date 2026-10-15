# Individual MM: chronological validation, not a production release

Research continuation on `ts-six-gw-validation-20261015`, PR #4. Production MM,
PM and TS equations are unchanged. `locked_model_active=false`; the legacy
2,125-point benchmark is a preserved reference, not a new candidate result.

## Scope and audit

The experiment extends `experimental_individual_role_mm.py` and
`experimental_mm_role_profiles.py`. It does not introduce an unrelated MM.
The original already uses recent start share, streaks, minutes, workload,
competition and rapidly weighted starter durations. The earlier start/survival
experiment adds regularized logistic start probabilities and individual hazards.
Consequently a plausible player example or a smoother duration is insufficient:
the relevant comparison is incremental accuracy over the same-feature logistic
control and the same XI projection, not only over the archived raw baseline.

Core has 27,283/29,747 final player-fixture observations in 2024/25 and 2025/26.
Neither season has populated matchday-squad or absence-reason fields in Core.
The new audit reconstructs *past* matchday membership from raw lineup sheets,
requiring unique canonical IDs, a uniquely mapped fixture, eleven matching
starter labels and agreement on club identity. Unmapped/ambiguous facts remain
unknown. A previous appearance also proves availability in that previous match.
An unknown zero-minute row is never an available tactical nonselection.

These postmatch facts enter only after kickoff+4h / +3h, respectively. These are
explicit conservative timing **proxies**, not source publication certificates.
Raw manifests and source hashes are in `data_audit.json`. Identity reconciliation
is retrospective and does not prove historical registration or roster clocks.
Confirmed historical bench membership is not a target-lineup feature.

There are no medically verified injury-return labels. `RETURNED_AVAILABLE`
identifies a predeadline news state, and a long gap is separately labelled a
non-medical proxy. No verified-injury subgroup metric is invented. The original
2025 news feed includes stale OUT states conflicting with 19 later appearances;
these cannot be repaired by consulting future outcomes. All role candidates and
the logistic control use the same archived availability caps. Missing target
news is an unconstrained uncertainty state, not an assertion of availability.

## Mathematical specification

Let K be an origin cutoff and t_j the proxy-known time of a previous fact. Only
`t_j < K` is admitted. Verified-squad observations receive calendar weights
`w_j = 2^(-(K-t_j)/H)`. A global position estimate is shrunk towards a finite
cold-history prior. A season/club/position estimate is shrunk towards that
position estimate with 40 pseudo-observations. The player estimate is

`r_i = (8 r_team,pos + sum_j w_j start_j) / (8 + sum_j w_j)`.

The starter-minute and cameo-minute conditional means use the analogous
position→club→player shrinkage, with five player pseudo-observations. The
conditional-squad cameo probability has eight pseudo-observations. These are
empirical-Bayes-style regularized estimates, not fully fitted Bayesian variance
hierarchies, causal roles, or calibrated posterior role-class probabilities.
Sparse players cannot acquire extreme profiles from one match.

Unknown or unavailable past matches add no starter-role failure. Sustained
verified benching changes the profile gradually; time without evidence shrinks
it towards its prior. This mechanism alone does not guarantee 90 minutes on a
return: baseline history and predeadline availability remain inputs.

The start model extends the previous L2 logistic MM, adding either continuous
profile statistics or broad descriptive role bands (r<.4, .4≤r<.8, r≥.8).
The fixed thresholds are a candidate simplification, not verified player
ontologies. Both variants include the baseline logit and its existing prefix
features. Candidate grids use H∈{42,180} days and C∈{.1,1}. The same learner
without role columns is retained as an information-redundancy ablation.

Log-odds projection preserves hard zeros/caps and ensures one expected keeper
and ten expected outfield starters per club fixture. Broad FPL positions cannot
identify actual tactical slots or justify imposing a fantasy-manager formation
on a real club. Thus these are feasible marginal constraints, not proof that an
independent simulator samples eleven starters. The legacy PM's independent-XI
physics are retained in paired PM comparisons and explicitly not certified.

For the full role arm, conditional-squad cameo odds are **not** directly
substituted for unconditional non-start appearance odds. A separate L2 logistic
calibration (C=.1, fixed before evaluation) learns the latter from earlier
observed non-start appearance outcomes, baseline q and prefix profile features.
Unknown squad status is still never coded as availability. All MM arms use
`E[M]=p s +(1-p)q c`; known OUT/SUSPENDED candidates set both p and q to zero.
The unchanged raw baseline and an availability-only diagnostic isolate that
existing composition bug from any role signal.

## Temporal protocol and uncertainty

Development/model choice: 2024/25 GW11–21. Start configurations minimize start
log-loss. Among selected-start, selected-start+duration and full-role arms, the
primary minute candidate minimizes all-row development MAE. Decisions are
written to `selection.json` before later-period metrics and 2025 predictions.
Fits always require completed labels strictly before their target cutoff.
Evaluation: 2024/25 GW22–38 and 2025/26 GW6–38, with previous completed-season
observations permitted. These seasons have repeatedly informed earlier
research: they are chronological evaluations, **not independent holdouts**.

Reports preserve Brier, log-loss, ECE10/reliability bins, minutes MAE/RMSE,
conditional starter/cameo diagnostics, and player/news subgroups. Paired 95%
bootstrap intervals use fixtures and, as a dependence sensitivity, club blocks.
They are conditional empirical intervals, not corrections for adaptive research
or proof of an independent generalization gain. Original MM, partition control,
availability-only, previous start/survival, role-start, role+duration, full role,
and same-logistic-without-role predictions use identical scored player-fixtures.

## PM and horizon validation

The PM factorial retains archived originals and rebuilds all MM-dependent
GA, defensive contribution, discipline and own-goal components. Baseline rebuilt
fields must match the archived input; frozen penalties/BPS/other components
are copied unchanged. Identical scoring, original seeds and 400 draws per
fixture are used. Selected role MM is paired with original PM and PR #3's fixed
player PM v2 hybrid configuration. The same logistic control is included under
both PMs to isolate role information. Ten point components must sum to xP.
Single-seed fixture intervals do not include all Monte Carlo uncertainty.

The separate GW+1…GW+5 diagnostic freezes each origin's known club/player state.
It selects horizon-specific convex shrinkage of original versus role forecasts
on 2024 origins GW11–16 with targets ≤21. It scores later origins without
updating from intervening outcomes. This is a measured conditional horizon
experiment, not a complete six-GW PM forecast: final fixture outcomes define
scored opportunities, future transfers can be unmatched, and actual historical
schedule-publication/roster/price clocks are uncertified. Uncalibrated rest-day
penalties remain zero. No TS replay is permitted by these diagnostics.

## Reproduction

Use the pinned dependencies and `PYTHONPATH=src:scripts`, under
`scripts/locked_numerical_runtime.py`. Restore the checksummed Core and 2024
checkpoint. Download the original MM inputs from Actions run 38565961308:
`mm-component-inputs-and-results`, `mm-original-pm-2024-25`, and
`mm-original-pm-2025-26`. Archive provenance is recorded in the result manifest.

1. Run `scripts/individual_mm_validation.py` (all candidates and reports).
2. Rebuild the same GW1 original source feature chain as the existing
   mm-component-research workflow; keep these research sources isolated.
3. Run `scripts/capture_individual_mm_pm.py` for each season with the selected
   candidate CSV and the corresponding original captured inputs.
4. Run `scripts/individual_mm_pm_replay.py --season ... --inputs ...`.
5. Run `scripts/individual_mm_horizon.py` and the existing six-GW input validator.
6. Run the role/profile, temporal, capture and relevant simulator regression tests.

Numerical results, completed checks and the final integration decision are
appended only after their actual runs complete.

## Completed minute results

The development start log-loss selects **bands, H=42 days, C=1**; the minute
arm choice retains the original duration/bench branch (`role_start`). The gap
to continuous H=42,C=1 in development log-loss is only 0.000053. A separately
preselected continuous alternative is evaluated without replacing the primary
choice after inspecting test results.

| MM | 2024/25 GW22–38 MAE / RMSE | 2025/26 GW6–38 MAE / RMSE |
|---|---:|---:|
| Original frozen | 12.653130 / 22.304667 | 10.533125 / 20.494545 |
| Previous start + survival mean | 12.683027 / 21.999201 | 10.893571 / 20.240319 |
| Same logistic, without role | 12.327796 / 22.100221 | 10.395341 / 20.338436 |
| Selected role-start | 12.308959 / 22.081301 | 10.387064 / 20.330737 |
| Role-start + duration | 12.736645 / 21.990817 | 10.788388 / 20.203858 |
| Full role, calibrated cameo | 12.951540 / 21.942938 | 10.964016 / 20.150785 |
| Continuous start alternative | 12.232433 / 22.066919 | 10.338120 / 20.267975 |
| Availability only | 12.653130 / 22.304667 | 10.354842 / 20.443038 |

The incremental selected-role MAE gain over the identical logistic control is
0.018836 minutes (fixture 95% interval delta −0.027805…−0.009805) in 2024 and
0.008276 (−0.012660…−0.003559) in 2025. Club-block intervals also exclude zero,
but the effect is very small. Incremental start-Brier and log-loss intervals
include zero in both seasons. The large raw-baseline improvement must not be
attributed entirely to the added role information.

| Start probability | 2024 Brier / log-loss / ECE10 | 2025 Brier / log-loss / ECE10 |
|---|---:|---:|
| Original | .081052 / .265987 / .013978 | .069635 / .228875 / .008707 |
| Same logistic | .080122 / .259891 / .004959 | .069420 / .228468 / .007557 |
| Selected role-start | .080019 / .259769 / .004296 | .069380 / .228435 / .007920 |

Availability reconstruction accepted 15,187 and 15,108 squad observations,
including 3,621 and 3,670 unused-bench rows; four lineup sides failed identity/
truth reconciliation. Another 54 played 2025 appearances prove past availability
without a validated squad-side map. Unknown availability remains 12,096/14,585
rows. There are 784/841 distinct canonical players in the full outcome seasons;
this is not a claim that all were in a historical deadline roster.

The horizon development chooses weight 1 for every horizon: there is no evidence
here for a newly learned decay or rest-day trajectory. Frozen role-start improves
MAE relative to the frozen original through GW+5, but the extra effect relative
to the frozen logistic control is only about .005–.025 minutes per scored row.
2025 GW+4's incremental interval includes zero. This is conditional evidence
on matched origin-club/player targets, not six-GW production certification.
The legacy forecast contract fails with **33/183** origin→target GW pairs.
No TS replay or new TS point total is produced.
