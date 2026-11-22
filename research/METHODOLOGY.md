# Statistical methodology v1

## 1. Information, estimands and evidence classes

Every prediction uses information set F_t genuinely available by its registered cutoff. Archive event time, source publication time where known, observation time, forecast issue/publication witness and deadline separately. A currently downloadable historical page is not proof of its historical version. Model/scoring-rule versions are part of the estimand.

Classify each result as: descriptive diagnostic; later reconstructed backtest; chronological out-of-time test with later-selected policy; genuinely prospective frozen test; oracle/sensitivity; or correctness proof over a declared finite domain. None is silently upgraded to another. A prediction can be genuinely issued before an outcome while a later-selected scientific hypothesis remains exploratory.

Players within one team/match share XI, substitutions, goals, CS and bonus. Matches share a GW and contextual shocks; repeated players and overlapping horizons add temporal dependence. Player-row count is never the independent sample size.

## 2. Targets and scores

| Model/target | Definition | Main evaluation / caveats |
| --- | --- | --- |
| MM start | P(start at the target fixture) | Brier and log loss, reliability by fixed probability bins; exact-11 aggregate balance is not individual calibration |
| MM appearance from bench | P(positive minutes AND not starting), plus q=P(positive minutes given nonstart) | Unconditional Brier and separate conditional Brier on actual nonstarters. Do not infer a start merely from minutes>0. Card-only official participation at 0 minutes is a distinct autosub target |
| MM starter/cameo duration | E[reported minutes given actual start] / E[reported minutes given actual bench appearance] | Conditional squared error and bias; same outcome-defined population for all models. MAE is descriptive, not the natural objective of a mean forecast |
| MM expected minutes | E[reported FPL minutes per fixture] | MSE/RMSE, MAE and bias; separate analytic MM means and Monte Carlo PM means |
| MM P60/P90 | P(reported minutes≥60), P(reported minutes=90) | Brier/log loss/reliability. Physical final-whistle exposure and reported FPL90 are different; record the clock definition |
| MM full law | Distribution over fixture minutes | CRPS/discrete log score, interval mass/coverage and tails. A DGW sum-of-minutes sample is not a per-fixture PMF |
| PM team goals | Full team score including opponent own-goals, or separately credited player goals | MSE of means; count log score/CRPS only with an actual archived count law. Never manufacture P(CS) from a mean by assuming a new Poisson law |
| PM player goals/assists | Counts under the season's FPL credit rules | Count MSE, probabilities/log scores when present; separate team volume, event eligibility and within-team shares. Observed post-shot xG/xA is another target, not the player's realized scoring count |
| PM CS | Team no-concession versus qualified on-pitch CS credit | Binary scores for identified team CS; qualification P60 and conditional on-pitch CS separately. Bounds from keeper conservation are identification intervals, not confidence intervals |
| PM DC | Counts and threshold-awarded points | Count law, threshold Brier, expected point error; season/position threshold fixed |
| PM keeper saves | Counts, save-point buckets and documented subtypes | Count/point scores with missing subtypes explicit; floor(saves/3) does not identify a full count distribution |
| PM BPS/bonus | Action BPS versus within-match bonus rank allocation | Verify deterministic rules with actual events, then model background/event forecasts and dependence separately. Bonus means cannot identify background-BPS error |
| PM total points | Full fixture/GW FPL-point law and mean | Primary proper CRPS for distributions, MSE/RMSE for means, bias, MAE, haul-Brier at prespecified thresholds, discrete interval mass/coverage |
| TS feasibility/search | Legal roster/FT/bank/chips and objective optimum in a stated domain | Exact bounded enumeration, scoring witnesses, legality counts and absolute/relative utility gap; heuristics need not be globally optimal |
| TS predicted utility | Utility of recommended action versus keep/minimal policy under the same original forecast | Paired objective delta with shared scenarios, official hits and original uncertainty penalties; expected gain is not realized gain |
| TS realized value | Observed net points of executed policies over complete state trajectories | Paired stateful policy comparisons with declared initial states, forecasts, prices, FT and chips. A recommendation, an intention and executed transfers are three separate objects |

For probability p and binary y, Brier=(p−y)^2. Log loss keeps genuinely impossible observed events visible: report zero-support failures; any numerical epsilon floor is explicitly labelled and applied equally to comparators. Do not silently hide structural failures by clipping.

Empirical CRPS = mean|X−y| − 1/2 mean|X−X'| from the archived sample, computed efficiently from sorted draws. Monte Carlo samples are integration draws, not new independent matches. Report draw count and simulation error where it may rival the proposed gain. No re-simulation for ordinary audits.

MAE is optimized by a conditional median, MSE by a conditional mean. A candidate's higher minute-MAE cannot alone reject a better mean/distribution model. Choose the primary proper score before seeing results. Brier/log loss can rank differently; secondary metrics do not replace a failed primary gate.

## 3. Validation, inference and multiplicity

Freeze baseline/candidate code and fit, source definitions, preprocessing, eligible population, primary score, periods and acceptance rules. Fit every ablation on prior labels only using the same training/development resources; zeroing a fitted component is a sensitivity diagnostic, not a refitted ablation. Test one information family while holding the rest fixed, and then test incremental downstream value.

Use chronological rolling origins; all labels in a training window must be known by that origin. Avoid random player-row splits and feature normalization learned on test data. Previously reused GW22–38 and GW8–10 remain development/exploratory. New planned MM/PM prospective work starts with a later forecast and new outcome; the old substitutions protocol keeps its own original eligible GW11 start.

Effect size is the paired score difference on the same players/fixtures, then aggregated using declared weights. Primary new-study uncertainty uses whole-GW paired resampling; fixture clusters are a sensitivity analysis and do not remove GW dependence. With material serial dependence, use prespecified contiguous GW blocks. Overlapping six-GW TS targets need nonoverlapping origins or blocks at least as long as the evaluated overlap; twelve overlapping origins are not twelve independent six-GW trajectories.

Report all-player and ex-ante active populations separately (e.g. frozen P(start)≥0.20); never select only observed scorers or the winning team's minutes. Club/player subgroups have sparse support and require counts; treat discoveries as exploratory or control multiplicity. For multiple new primary comparisons use a prespecified family and Holm adjustment or clearly prioritize one comparison. No repeated peeking or switching endpoints after a small p-value. Existing registered gates are not retrospectively rewritten.

Intervals include sampling uncertainty conditional on the model/data protocol. They do not automatically include policy selection, source revisions, nonstationarity, fit uncertainty, or all Monte Carlo error. Three GWs do not justify asymptotic precision or reliable GW-level power estimates.

## 4. Achievable accuracy: defined mathematics, limited identification

Let m(F)=E[Y|F]. For a fixed fitted predictor f and an independent future evaluation:

E[(Y−f(F))²] = E[Var(Y|F)] + E[(m(F)−f(F))²].

The first term is Bayes risk relative to the specified information set; the second is excess prediction risk. With random training data there is further model/training variation when averaging over fitted f. For binary outcomes the analogous decomposition is E[p(F)(1−p(F))]+E[(p(F)−p_hat(F))²]. Expected log loss is conditional entropy plus excess KL risk; proper distribution scores have their own model-dependent risk baselines.

We do NOT observe m(F) or Var(Y|F) from one outcome per fixture. There is no certified numerical Bayes bound here. “Aleatoric” is irreducible only relative to F; adding a lawful predeadline injury report changes F and may reduce conditional uncertainty. Epistemic uncertainty includes finite data, model misspecification, source/missingness errors and parameter estimation.

Programme for EXP-LIMITS-001:

1. Define information sets F0/F1 explicitly; use matched future periods and identical target units.
2. Build learning curves using increasing prior-only training blocks, keeping a common untouched evaluation origin and a separately selected model class. Account for seasonal drift and roster changes; an asymptote from a short nonstationary curve is not a noise-floor proof.
3. Fit alternative conditional uncertainty classes with cross-fitted/out-of-time residuals. Model disagreement and learning curves give model-dependent epistemic diagnostics, not identified true uncertainty components.
4. Compare lawful simple, current and alternative model classes. Better performance than one weak baseline does not show closeness to optimality.
5. Reuse start/minute/score-component oracle sensitivities with explicit support and selection limits. Conditioning on actual minutes or team goals uses future information. It is neither a deployable model nor a proven lower bound on original-information Bayes risk. Estimated oracle corrections can even worsen empirical risk under misspecification.
6. Report ranges and failed assumptions. Never report “we are X% of optimal” without a mathematically defined, justified denominator and uncertainty. No such denominator is established by PR41/42.

Existing three-GW data support descriptions/oracles and bookkeeping. Two reused seasons may support method development and learning-curve pilots, subject to cutoff and rule-year controls. They do not provide pristine model-selection validation or an identified ceiling. New prospective rounds are necessary for confirmatory gain claims.

## 5. TS experimental separation

First test legality and search with fixed synthetic payoffs, before any forecast-policy claim. Exact-small protocol has two levels: (A) pool≤17, ≤2 transfers, deterministic all-play fixtures; exhaustive legal XV/XI and captain selection, where vice/bench order cannot change deterministic all-play utility; (B) a declared small nomination menu with DNP/vice/autosubs, ≤8 scenarios and full enumeration within that menu. LevelB is not a global optimum over excluded nominations. Use hand-derived witnesses and never compare different scorers.

Then compare keep-squad, minimal-necessary-transfer and original TS policies from identical original states. Document sale prices, bank, FT transitions, captain/vice, hits, eligibility and chip states at each origin. Saving a FT has an opportunity value only in a coherent subsequent state, not by retroactively choosing whichever path later won. Distinguish one-step controlled actions from stateful season trajectories.

Horizon length, discounting, hit buffer and risk-penalty sensitivity are proposed separate arms, not authorized parameter optimization now. Select on prior development blocks only, reserve new trajectories and preserve full origin/target vintages. Chip tests require relevant complete option horizons and actual availability; chips-OFF season totals cannot validate WC/FH/BB/TC.

## 6. Acceptance and reporting

New efficacy acceptance requires a meaningful prespecified effect on a proper score, appropriate paired uncertainty excluding no gain, data/cutoff/identity/legality gates and downstream/subgroup safeguards. Exact correctness uses proof over a declared finite set and zero invalid outcomes, not p-values. New-study minimums and power plans are protocol-specific. “Accepted” is a research decision; deployment still needs an independent integration PR, frozen regression comparison, rollback and privacy checks.
