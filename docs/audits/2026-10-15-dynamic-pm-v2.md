# Dynamic reliability weights in player PM v2

Research in PR #3, based on `0e1117d`. Production MM/PM/TS/chips, reference outputs and the 2,125-point benchmark are unchanged. `locked_model_active=false`. No manager data is used. Numerical matrix: [38772814007](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38772814007), numerical commit `72b61e4`. Results must be taken from completed artifacts, not inferred from the equations below.

## What the existing 75/25 choice means

The previous development search used 2024/25 GW6–21, selecting a 365-day calendar half-life and five 90-minute pseudo-exposures for the simple/hierarchical player profiles. It screened anchor weights h in {0.25, 0.5, 0.75} and aggregate creative elasticities beta in {0, 0.25}, minimizing team-xG quasi-Poisson deviance of analytic expected-MM exposures. It selected h=0.25, beta=0.25. It did **not** select weights by FPL-point accuracy, claim an optimal universal reliability ratio, or blend actual goals with xG in a 75/25 ratio.

At minute t, let Q(t) be opponent/venue-adjusted player chance production, A(t) adjusted player creativity, lambda_0 the unchanged team forecast and C(t)=[A(t)/A_anchor]^0.25. The chance layer is

    X(t) = [w Q(t) + (1-w) lambda_0] C(t), with w=0.75 previously.

Finishing, the ordinary-goal/penalty split, scorer shares and attached assists follow this layer exactly as in the existing PM v2. The gate changes only w. Both analytic endpoints used to learn the gate include the same C; the team endpoint lambda_0*C is therefore distinct from the original PM's lambda_0. Neither creativity nor finishing is disabled in the fixed versus dynamic comparisons. Individual goal intensities still sum to the team process.

## Isolated gate candidates

* **Fixed:** w=0.75, reproducing the previous independent-XI candidate to CSV round-trip tolerance 1e-12 per xP value.
* **Data amount:** average n_i/(n_i+k), where n_i is calendar-weighted prior minutes/90 in the matching FPL role. Test k=5,20,80. Average with predeadline MM start mass, or, as a more detailed alternative, with expected xG contributions. No target XI is used.
* **Conditional profile uncertainty:** w=1/(1+k V/Q²), k=1,4,16, with V the sum of squared expected-exposure-weighted Gamma-profile SDs after opponent/venue/creativity adjustment. This is deliberately a simple candidate, not a claim that independent-profile variances describe total forecast uncertainty.
* **Correlated forecast errors:** fit nonnegative a,b in E[e_player²|V]≈a+bV using resolved earlier team-xG forecasts. Let m_T=E[e_team²], c=E[e_player e_team]. Then w=clip((m_T-c)/(m_P+m_T-2c),0,1). Compare full c and 0.5c. Cauchy–Schwarz bounds on c preserve feasible second moments when conditional m_P changes. Bias is included in second moments; correlation is never assumed zero. Degenerate equal-error moments fall back explicitly to 0.75.
* **Regularized learned gate:** w=sigmoid(b0+b'z+u_season,team). Standardization uses preceding training rows only; optional season/team effects have zero cold-team offset. Fit squared team-xG forecast error plus k/N times the squared distance from the 0.75 intercept/zero-slope prior, k=0.1,1,10. Inputs: prior minutes, history coverage, conditional relative variance, new-player/club-change/role-change mass, difference from the latest known XI, recent team-xG variability, endpoint disagreement, absence-return proxy and explicit missing-history indicators. Fewer than 40 resolved team sides use the explicit 0.75 prior.

The absence proxy means two known registered zero-minute appearances and at least 14 days since a known played appearance. It is **not** a verified injury/medical-return label. Club/role change flags retain the preceding model's limitations: broad FPL positions and observable within-season club transitions; a verified summer-club bridge and tactical role histories are missing. Unavailable sources are not invented.

## Time ordering and selection

Gate development uses 2024 GW6–13 as a warm prefix and chronological GW14–21 validation. A gate fitted for deadline c can only see outcomes whose inherited known time is strictly less than c. Select one configuration per family and one overall dynamic family by development xG deviance, persist selection, then open later forecast captures. Evaluation is 2024 GW22–38 and 2025 GW6–38. Online refits may use earlier resolved evaluation matches; hyperparameters cannot change. IDs are scoped by season and team.

The underlying frozen player-profile hyperparameters were selected using the earlier research's whole 2024 development period. Thus internal gate validation is not an untouched validation of the entire profiling pipeline. All these seasons have also been reused in previous experiments. Historical known times remain kickoff+3/4-hour proxies, not verified publication times. These limits preclude production certification or claims of pristine holdout evidence.

## XI experiment and scoring controls

The bridge calls the **existing** `experimental_correctness_simulator.sample_intervals`. Its odds-projected start marginals and dependent rounding yield exactly 11 starters and one GK per team. Existing substitution slots, maximum five substitutes and substitution windows prevent overlapping active slots. Each draw asserts 11 starters/one GK, no >11 simultaneously active players, no >1 active GK and no hard-unavailable participation. There can be vacancies after exits. FPL manager formation bounds are not real-world formation constraints and are not added.

The original and player PM receive identical MM inputs and feasible legal start marginals. Marginal projection is recorded, not concealed as unchanged raw Bernoulli probabilities. Gates use the same predeadline original-MM probabilities across XI layouts. No realized target lineup or minutes enters a forecast.

The bridge replaces only minutes/interval generation and retains the original shared simulator's **same legacy own-goal, clean-sheet, penalty, special-assist and scoring semantics in every comparison arm**. It does not silently enable the previous whole-simulator own-goal correction in just one arm. Consequently this experiment isolates XI and weighting effects, but does not certify all known scoring issues as resolved. An additional own-goal-physics ablation would be separate.

For experimental survival MM, starter durations come from its same frozen hazard distributions inside the legal sampler. Its existing legal-starter one-minute floor clamps any sampled zero to one; counts are exported. This is explicit and common to all legal experimental-MM PM arms. Within each comparison MM is held constant.

## Historical matrix and evidence

Frozen public prepared records come from successful prior run `38729720330` (`852f237`): 330 fixtures/GW6–38 per season/MM, immutable seeds and profiles. Source captures are gzip-validated. Independent locked-MM original xP must reproduce the original captured reference exactly, and independent fixed75 must reproduce the preceding candidate. Every model's point components must reconcile to xP. Each replay uses 400 draws, two workers and a fixed numerical runtime. Six deterministic fixture shards per context allow complete checks and signature caches.

The six season/context arms are 2024/2025 × locked-MM independent XI, locked-MM legal XI and experimental-MM legal XI. Locked legal arms compare original, fixed75 and all four selected dynamic families; the other arms compare original, fixed75 and the development-selected dynamic family. Original-to-original across XI isolates the XI change. Fixed-to-fixed across XI also isolates that change. Within legal XI, fixed-to-dynamic isolates the gate. Experimental MM is evaluated separately, never conflated with the PM effect.

Metrics include team-xG/goals MAE/RMSE/deviance/calibration, player goal/assist proper scores, xP/bonus/BPS, clean-sheet Brier and on-pitch conceded-goal MAE. Fixture-block paired bootstrap intervals preserve same-match dependence. The follow-up audit uses predeclared development-median reliability bins, conditional profile variance versus actual forecast-error moments and exact Shapley point-error decomposition (algebraic attribution, not causality). Six independent common seeds on the first two later fixtures per season/MM measure conditional Monte Carlo dispersion; those selected fixtures cannot establish a whole-season statistical gain.

No full historical MM→PM→TS candidate score is claimed: complete six-GW forecast origins are still missing. The original 2,125-point benchmark is preserved rather than compared with a fabricated replay. Tests at initial commit: **544 passed**, including 12 new gate/XI regressions. Completed numerical evidence and the recommendation are below.

## Completed development selection

The selection job succeeded before any later replay job started. Chronological 2024 GW14–21 validation selected the following frozen configurations. These are development scores, not independent evidence of improved FPL accuracy.

| Gate | Frozen configuration | xG deviance | Mean player share |
| --- | --- | ---: | ---: |
| Fixed | 0.75 | 0.34786894 | 0.750000 |
| Data amount | individual xG-contribution-weighted n/(n+20) | 0.34586850 | 0.455749 |
| Conditional uncertainty | 1/(1+16 V/Q²) | 0.34805997 | 0.758316 |
| Correlated errors | 0.5 × past cross-moment | 0.34687232 | 0.579713 |
| Learned | no team offsets, ridge strength 10 | 0.34803180 | 0.749369 |

Overall selection: **data amount**, relative development deviance reduction 0.575% versus fixed75. This is a fairly small selected gain after screening 18 configurations; its out-of-period performance is decisive. Team offsets did not win the predeclared deviance criterion. The more detailed data candidate computes reliability for each player before xG-contribution-weighted aggregation; it remains a scalar team/game gate and does not introduce a separately tuned scorer-allocation model.

Shared initial seeds do not ensure identical later lineups when changed goal counts alter RNG consumption. The sampling law and MM inputs are identical within an arm; follow-up multi-seed dispersion is reported separately from fixture-bootstrap uncertainty. Conditional profile variance omits future match/opportunity variation and common parameter, context and role uncertainty: a large residual/conditional-variance ratio is not, by itself, proof that individual latent Gamma credible intervals are miscalibrated. Raw Actions artifacts have 90-day retention; committed report hashes establish source identity but are not a permanent archive of all raw replay bytes.

## Completed historical matrix

All **38 jobs** in run 38772814007 passed: selection,36 replays and aggregation. The 24 model/season cells each replay 330 fixtures at 400 draws: **3,168,000 match draws**, including 2,376,000 legal-XI draws. Later-period scoring uses 13,105 player/fixture rows per model in 2024 and 26,159 in 2025. Registered nonparticipants are included; played-player and prior-role groups are also exported. Original independent-XI references reproduce exactly and fixed75 reproduces the preceding PMv2 candidate. Every component sum reconciles. No production model changed.

| MM | XI | PM | 2024 xP-MAE | 2024 RMSE | 2025 xP-MAE | 2025 RMSE |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Locked | Independent | original | 0.94779378 | 1.84814559 | 0.92917266 | 1.88070713 |
| Locked | Independent | fixed | 0.94954693 | 1.84393802 | 0.92952827 | 1.87857013 |
| Locked | Independent | amount | 0.94839203 | 1.84450076 | 0.92891510 | 1.87822342 |
| Locked | Legal | original | 0.94690424 | 1.85013908 | 0.92630070 | 1.87924161 |
| Locked | Legal | fixed | 0.94626021 | 1.84909827 | 0.92519343 | 1.87765765 |
| Locked | Legal | amount | 0.94720527 | 1.85023194 | 0.92645657 | 1.88002554 |
| Locked | Legal | uncertainty | 0.94615166 | 1.84725583 | 0.92481163 | 1.87800108 |
| Locked | Legal | covariance | 0.94786761 | 1.85146802 | 0.92664848 | 1.88041616 |
| Locked | Legal | learned | 0.94726631 | 1.85040602 | 0.92567061 | 1.87843605 |
| Experimental | Legal | original | 0.92439928 | 1.84260686 | 0.91566717 | 1.86853762 |
| Experimental | Legal | fixed | 0.92645899 | 1.84240519 | 0.91391204 | 1.86508020 |
| Experimental | Legal | amount | 0.92553243 | 1.84149988 | 0.91517461 | 1.86727718 |

2024 means GW22–38;2025 means GW6–38. Development-selected dynamic family is `amount`; the other families were selected within their own development grids. They are not retrospectively substituted for the overall winner.

### Gate effect with locked MM and legal XI

Paired point-MAE difference versus fixed75; negative is better. Intervals are2,000 fixture-block bootstrap draws, not multiplicity-adjusted and not a pristine-holdout claim.

| Dynamic gate | 2024 ΔMAE [95% CI] | 2025 ΔMAE [95% CI] |
| --- | --- | --- |
| amount | +0.0009451 [-0.0017523;+0.0035498] | +0.0012631 [-0.0005395;+0.0032254] |
| uncertainty | -0.0001085 [-0.0022867;+0.0021153] | -0.0003818 [-0.0017918;+0.0011186] |
| covariance | +0.0016074 [-0.0007067;+0.0040290] | +0.0014550 [-0.0003279;+0.0033160] |
| learned | +0.0010061 [-0.0000660;+0.0020827] | +0.0004772 [-0.0006035;+0.0015046] |

The selected amount gate is slightly worse than fixed75 on both legal-XI point MAE and RMSE. Its apparent independent-XI MAE gains do not survive the XI correction. The uncertainty gate has slightly better legal-XI MAE in both seasons, but both intervals cross zero and2025 RMSE is worse. Covariance/learned gates do not establish a point gain. Picking uncertainty after seeing these evaluation tables would be a new selection, not independent confirmation.

Under experimental MM, amount improves point-MAE versus fixed75 in 2024 by0.00092655 but worsens2025 by0.00126257; both intervals cross zero. This does not support a robust MM interaction benefit.

### Team and individual events

| Season | Legal-XI PM | Team xG MAE | Team goal MAE | Goal deviance | Individual goal MAE | Individual assist MAE |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2024-25 | original | 0.58402018 | 0.91555655 | 1.10202640 | 0.06219783 | 0.05893800 |
| 2024-25 | fixed | 0.57376550 | 0.90429146 | 1.08617191 | 0.06076822 | 0.05760855 |
| 2024-25 | amount | 0.57402430 | 0.90642551 | 1.08762147 | 0.06141454 | 0.05817913 |
| 2025-26 | original | 0.58540967 | 0.89064955 | 1.05212244 | 0.05740261 | 0.05558393 |
| 2025-26 | fixed | 0.58138442 | 0.87850752 | 1.04718952 | 0.05709068 | 0.05500755 |
| 2025-26 | amount | 0.58097850 | 0.88110147 | 1.04640582 | 0.05742163 | 0.05525622 |

Fixed75 retains promising team-goal performance versus original PM under legal XI:2025 goal-MAE difference−0.0121420 [−0.0223758;−0.0008536]. This is not evidence that dynamic weighting improves it: amount's2025 goal MAE0.88110147 is worse than fixed's0.87850752, despite slightly lower xG MAE/deviance. Full reports include goal/assist Brier, log loss, Poisson likelihood, calibration bins, bonus/BPS, on-pitch concessions and clean-sheet Brier. Original team lambda is used as its unchanged xG/goal-intensity forecast, not a newly fitted pure chance model. Player-PM goal forecasts are intensity proxies from the existing ordinary/penalty layer; legacy own-goal semantics remain a limit.

### XI effect and remaining minute-model inconsistency

Correcting XI changes model rankings: fixed75 MAE falls0.94954693→0.94626021 in 2024 and0.92952827→0.92519343 in 2025. Original PM MAE changes0.94779378→0.94690424 and0.92917266→0.92630070. These are XI/marginal/substitution changes, not dynamic-weight improvements.

Maximum individual raw-to-feasible start-marginal adjustments are **22.0525 percentage points in 2024** and **62.3945 points in 2025 locked MM**. Thus the legal sampler cannot preserve every original independent start probability: the raw probabilities are not always jointly feasible. Within each legal-XI PM comparison, projected probabilities are identical and availability constraints are unchanged. Experimental MM's2025 projection change is at floating-point scale (~6.2e−14), while2024 still includes the22.0525-point maximum. This is a material MM/input diagnostic, not an improvement achieved by changing PM weights.

### Recommendation

**Do not promote dynamic weights.** Keep fixed75 as the frozen PMv2 research reference and keep original production MM/PM/TS/chips unchanged. A tiny development xG gain did not translate into a robust out-of-period point improvement under legal XI. The full-simulator comparison is more informative than the analytic screening objective. Legal-XI integration and profile calibration deserve further independent validation before production decisions. `locked_model_active=false`; no new TS season total or live certification is claimed.

## Reproduction and preservation

Research entry points: `experimental_dynamic_pm.py`, `research_dynamic_pm_v2.py` and `postprocess_dynamic_pm_v2.py`. The first workflow selects, runs all 36 shards and aggregates; the evidence workflow pins that successful run and separately diagnoses/exports it. Both require Python 3.12 and the existing pinned numerical requirements. Selection/replay/MC are launched via `locked_numerical_runtime.py`. Restore Core with `scripts/restore_core_checkpoint.py`; prepared source files come from the 16 `player-pm-v2-20*` artifacts of run 38729720330. Selection writes `*_features.csv.gz` and `*_weights.csv.gz` before simulation. The following stages are independently callable:

```sh
python scripts/locked_numerical_runtime.py scripts/research_dynamic_pm_v2.py --stage select
python scripts/locked_numerical_runtime.py scripts/research_dynamic_pm_v2.py --stage replay --season 2024-25 --mm locked --layout legal --shard 0
python scripts/research_dynamic_pm_v2.py --stage aggregate
python scripts/postprocess_dynamic_pm_v2.py --stage diagnose
python scripts/locked_numerical_runtime.py scripts/postprocess_dynamic_pm_v2.py --stage mc
```

Replay all six shards for each of the six season/MM/XI contexts before aggregation; an incomplete matrix fails. Full production-preservation check: every preexisting tracked file at 0e1117d is unchanged by this task's code commits; all 60 preexisting `src` files were checked byte-for-byte. Their SHA-256 values are in `baseline_preservation.json`. Full audit [38774188180](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38774188180), at 9fac2d1, passed 546 tests, existing numerical reproductions and benchmark preservation (`2125`,33/183 horizon cells). No claim of a new candidate TS score is made.

Publication clocks, genuine medical-return labels, tactical/summer-transfer histories and an independent validation period remain missing. The same legacy scoring semantics used here isolate the gate comparison but do not resolve all known simulator certification issues. A future study of corrected own-goal physics must apply the correction to all PM arms together. The bridge has the documented starter-duration floor, but **zero floor/clamp events actually occurred in these historical replays**; it did not numerically explain their differences. Between-MM comparisons are still not a pure PM treatment effect.

## Why the tested gates did not establish a gain

The completed reliability audit gives the following analytic endpoint diagnostics under locked MM. The team endpoint includes the same creative factor as the player endpoint; it is not the unmodified original PM.

| Evaluation | Endpoint residual correlation | Player forecast MSE | Conditional profile V | MSE/V | Amount mean w | Learned mean w |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 0.973000 | 0.532251 | 0.039473 | 13.484 | 0.486529 | 0.740492 |
| 2025 | 0.977348 | 0.552361 | 0.044888 | 12.305 | 0.462319 | 0.736938 |

The two forecasts largely share errors. Treating them as independent estimates would exaggerate the benefit of combining them. Conditional profile variance represents a small part of total realized forecast error; it omits opportunity variation, MM/role/context and shared-parameter uncertainty. This does not prove miscoverage of latent individual Gamma intervals. The NNLS error-floor/cross-moment candidate was explicitly tested, rather than assuming inverse variance is optimal; it still did not improve point accuracy. The learned gate's strong development-selected regularization keeps weights close to75%, consistent with limited distinguishable forecast-error signal rather than evidence for a highly flexible gate.

The amount gate deliberately moves much closer to the team anchor. That lowers development analytic xG deviance but does not consistently improve individual events or legal-XI point accuracy. Gate training uses analytic expected exposures, whereas evaluation uses the projected legal joint XI and full nonlinear event/point process. The ranking reversal across XI layouts demonstrates lack of transfer of the selected gain; it does not establish a unique causal explanation. A future legal-exposure-trained gate would be a new experiment requiring its own development selection and fresh validation, not a retrospectively validated result of this study.

### Current point-error attribution is not the previous clean-sheet story

Exact Shapley attribution of amount-minus-fixed point-MAE, locked MM/legal XI:

| Component | 2024 contribution | 2025 contribution |
| --- | ---: | ---: |
| Goal points | +0.00139225 | +0.00086938 |
| Assist points | +0.00028082 | +0.00043478 |
| Clean-sheet points | −0.00082127 | −0.00050550 |
| Bonus | +0.00020415 | +0.00015999 |
| Total, all ten components | +0.00094506 | +0.00126314 |

Here the goal/assist terms deteriorate while CS offsets some of the loss. It would be incorrect to repeat the preceding independent-XI study's explanation that goal/assist gains are lost to CS. Clean-sheet **Brier** nevertheless gets worse (.05939690→.05977780 in 2024; .05678058→.05703216 in 2025): probability loss and weighted point-MAE attribution are different quantities. Shapley is algebraic prediction-error attribution, not causality. Changed RNG consumption also changes sampled lineups and unchanged components' realized averages.

### Cohorts, source gaps and simulation precision

The initial binary any-new-player/any-return-proxy flags saturated because tiny fringe-player start mass existed in almost every roster. This **reporting defect** was corrected in140387a: all continuous reliability fractions use frozen2024 development-median splits, with no gate/forecast/model-result change. Sparse groups carry fixture counts and explicit inference warnings. Historical tactical/medical return claims remain Not Available; a proxy is not evidence of a real injury return. Broad-role changes are absent in the 2024 evaluation and very sparse in 2025. Isolated exploratory subgroup intervals are not a production-selection rule and are not adjusted for all comparisons.

[Completed six-seed evidence38774188162](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38774188162) adds86,400 match draws on the first two later fixtures per season/MM. For amount versus fixed under locked MM, conditional seed-SD of the mean MAE difference is0.009066 in 2024 and0.004830 in 2025; mean differences are+0.001684 and+0.009417. These are small fixed-fixture diagnostics, not whole-season confidence intervals. In2024 the signs vary by seed; in 2025 those two fixtures deteriorate in all six seeds. This neither establishes general superiority nor rules out very small effects. More seeds/common-lineup random streams would help assess tiny candidate differences before any future promotion.

All 100,462 player-profile cutoff checks passed, as did the target-side and fitted-label maximum-known checks, **under the inherited availability proxies**. Both legal historical MM arms had zero duration clamps. All 11 exported report files were initially recovered byte-for-byte against their original SHA-256 values; the corrected cohort report is exported and verified separately without rerunning or changing the historical or seed simulations. Model and metric gains remain diagnostic and non-independent.

Final cohort export [38777082642](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38777082642) passed at 140387a. All 11 final report hashes match their source exports; only `reliability_report.json` changed from the first export. The corrected higher-new-profile groups contain 111/222 team sides (2024/2025), instead of every team. Amount-minus-fixed point-MAE is+0.001776/+0.000523 in those groups, so they do not demonstrate the desired consistent benefit. These are exploratory cohorts, not independent acceptance tests. The sparse 2025 broad-role-change group has only 10 fixture blocks and is explicitly marked insufficient for reliable inference.

Final local regression suite: **547 passed in 31.07s**, including the new cohort-saturation/development-cutoff regression. Existing full audit at 9fac2d1 remains separately identified as 546 passed; later automatic audits are not silently counted as completed. The durable `evidence_manifest.json` distinguishes primary numeric code, six-seed code, corrected reporting code and final evidence publication.
