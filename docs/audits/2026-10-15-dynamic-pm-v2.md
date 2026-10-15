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

No full historical MM→PM→TS candidate score is claimed: complete six-GW forecast origins are still missing. The original 2,125-point benchmark is preserved rather than compared with a fabricated replay. Tests at initial commit: **544 passed**, including 12 new gate/XI regressions. Recommendation must wait for actual completed numerical evidence.
