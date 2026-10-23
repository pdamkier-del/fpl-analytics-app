# Complete ordinary-goal / penalty separation in B

This supersedes the rejected partial ablations documented in `2026-10-23-penalty-boundary.md`. The user explicitly requested completion of the separation after those ablations. Production/default calculations remain unchanged; this release targets the existing B preview.

## Implemented boundary

The ordinary-goal head now receives only count-based FPL-scale nonpenalty xG: historical xG minus 0.79 for each verified scored **or missed** penalty. This is an explicitly approximate NP estimate, not native per-shot npxG. Verified penalty identities and complete match coverage are required. Materially negative residuals fail closed.

Individual recency rates, broad position priors, soft tactical-role priors and short-form features all use that same NP history. The two recent features are the last known PL npxG and the weighted last-three known PL npxG. No penalty goals, inclusive xG, old inclusive performance coefficients or player-name override enter this ordinary-goal head. All-competition role/MM inputs and the existing assist head remain unchanged; missing cup information is not inserted as zero NP performance.

The existing shared allocation fitter is refitted to **NP-xG targets**, using its fixed L2=200 regularization. Individual goal-rate half-life and shrinkage exposure are also refitted to NP targets on the existing 2025/26 GW16–21 development window. They become 11.4833 observations and 592.7757 minutes, respectively. Training uses 4,670 player-fixture rows; no validation outcome chooses these parameters. Old inclusive training metadata is removed from the publication model; numerical equivalence with the validation input is archived explicitly.

The penalty channel retains team occurrence, taker conversion shrinkage and current official ranks. Its zero-history fallback is now frozen in its own `penalty_fallback_weight` before replacing ordinary scorer weights. Changes in the ordinary head cannot change this fallback. The expected scored-penalty mass removed from the inclusive team goal mean uses the actual active lineup and the exact same taker/conversion rule as the penalty event sampler. This gives:

```
ordinary team goal mean = inclusive team goal mean - conditional expected penalty goals
ordinary scorer weights = NP-only fitted head
penalty taker weights/ranks/fallback = separate penalty channel
```

A synthetic extra penalty added to inclusive history, with its verified event count, leaves every NP rate, role prior, short-form feature and ordinary scorer weight unchanged. Separate tests change ordinary weights radically and verify unchanged conditional penalty conversion and identical penalty outcomes in seeded fixed-lineup draws. Misses, saves and all goal/point components reconcile.

## Validation and interpretation

The new protocol was fixed **before this fully refitted candidate was scored**. It tests mathematical separation and xP MAE noninferiority: overall delta <=0.005 and played-player delta <=0.02 in each season. This differs explicitly from the earlier ablation gate, which required no increase at all in penalty-taker absolute bias. We do not relabel that failed gate as passed. The new user-requested correction removes the blended head rather than preserving its compensating errors; all subgroup bias changes remain visible below.

Both seasons use only GW22–38: 171 fixtures in 2024/25 and 170 in 2025/26, 341 in total, 400 draws per arm. Thus GW16–21 training rows are excluded from evaluation. The earlier-season comparison remains a conditional robustness replay because the existing baseline and the new model both use models selected later; neither it nor the reused 2025 period is independent certification. Every baseline xP reproduces the archived joint-role B baseline exactly (maximum difference 0).

| Metric | 2024/25 before → after | 2025/26 before → after |
|---|---|---|
| All-player xP MAE | 0.887523 → 0.889075 | 0.870576 → 0.870893 |
| Played-player xP MAE | 1.887461 → 1.890859 | 1.994181 → 1.993161 |
| Penalty-taker xP MAE | 2.380330 → 2.327094 | 2.326152 → 2.280511 |
| Penalty-taker xP bias | -0.032318 → -0.207585 | -0.042379 → -0.203337 |

The MAE noninferiority gate passes. **Overall predictive accuracy is not improved**, and systematic underprediction in the historical taker cohort worsens. This is a B-only correctness release, not a production promotion or a claim that all penalty calibration is solved. A full penalty-winner-assist process remains absent. The confidence intervals and complete scored rows are retained with the decision.

On the fixed current release reference, 60 fixtures / 4,008 player-fixture rows / GW8–13 are replayed. The old B baseline is reproduced exactly. Every analytical minute/start marginal is unchanged. Le Fée's GW8 xP is 5.52 → 4.6625; his xM and start probabilities are unchanged. This is a paired reference result, not necessarily the value after a later official source refresh.

## Public transparency and release gates

Each B fixture publishes separate expected ordinary and penalty goals, expected misses, player probability of taking/scoring at least one penalty, and the team's Poisson probability of at least one penalty. These fields are derived from the same PM draws, with no extra RNG calls; they reconcile to total goal points and the missed-penalty subset of negative points. The existing player card gains a closed details panel beneath its match forecast table, retaining the original desktop layout.

The release requires checksum-pinned NP policy/model/evidence, exact historical replay in CI, unchanged original seeded PM behavior, fresh current data, repeated full six-GW output, exact one-match and one-GW/full-horizon comparisons, the existing TS on a legal synthetic state, public browser verification, and unchanged production assets. Current before/after controls use the **same fresh facts, MM, role kernel and seeds**; no private user roster or transfer is changed.

Reproduce the fit with `analysis/fit_nonpenalty_allocation.py`, the paired holdout with `analysis/test_separated_goal_head.py`, and the prospective current comparison with `analysis/test_current_penalty_candidate.py --model ...`. Use `scripts/locked_numerical_runtime.py` and `PYTHONPATH=src:scripts:.:analysis OPENBLAS_NUM_THREADS=1`.

The final short-form correction excludes zero-minute registrations, so resting a player does not manufacture a bad attacking performance. The final fit and validation are in `final-v2` and `separated-goal-head-v2-validation-20261023`; the first refitted prototype is retained separately for transparency. This change addresses absence semantics, not validation-metric tuning.

Displayed team/player penalty probabilities share the same Monte Carlo event denominator, so a player cannot have a larger displayed chance than his team. The exact analytical Poisson probability is retained separately as `team_p_at_least_one`; the displayed common-draw parent is `team_simulated_p_at_least_one`. This summary-only change makes no extra RNG calls and changes no xP, minute, goal or scenario outcome.
