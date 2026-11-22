Own goals previously bypassed shared conceded/clean-sheet events, and independent start sampling could produce invalid starting XIs. This PR adds an isolated opt-in simulator candidate: timestamped own-goal scoreline events without fictional goals/assists; reconciled ordinary/penalty/own-goal goal budgets; exact one goalkeeper plus ten outfield starters through marginal projection and dependent rounding; non-overlapping substitute slots with normal substitution/window limits.

The locked production simulator, fitted parameters, original MM/vFinal/TS/chip decision functions and benchmark remain unchanged. No production deployment, merge or live certification; `locked_model_active=false`. Candidate activation exists only in serial offline audit scripts.

A 2024 evaluation-adapter exposure bug discovered during A/B counted only penalty-event matches in occurrence denominators. The adapter now counts all cutoff-available fixture-side exposures, retaining the original formulas/coefficients. Both sides of the 2024 comparison were recomputed on those same corrected inputs.

### Verified historical A/B
330 fixtures per season, GW6–38 current-GW origins, 400 draws/original seeds, no rejected fixture-mode evaluations.

| Season / rows | Original point MAE | Combined candidate MAE | Paired delta / fixture-block 95% interval |
| --- | ---: | ---: | --- |
| 2024/25 / 24,072 | 0.991189 | 0.987544 | -0.003645 [-0.005369, -0.001872] |
| 2025/26 / 26,159 | 0.929173 | 0.923335 | -0.005838 [-0.007667, -0.003946] |

Precision remains mixed: 2024 point RMSE 1.898567→1.899665; played-player minute MAE 22.105592→22.401269. 2025 played-player minute MAE 20.675466→20.908438 and played-player point RMSE 2.924622→2.926763. Development-period bootstrap improvements do not establish independent OOS acceptance. Separate own-goal-only and XI-only results are in the committed reports.

### Haaland, Chelsea and Saka
Audited cutoff 2026-10-12T10:45:27.093744+00:00, eight independent 400-draw GW7 seeds:
- Haaland simulated minutes 66.876563→67.933750; xP 5.511563→5.547500. P(start) 83.823042%→83.815771%.
- Saka xP 5.545000→5.580313; minutes 81.492813→81.449375.
- Chelsea total goal intensity stays exactly 1.342868819888325; no extra goal mass is added.
Both player xP seed-variation intervals include zero. Haaland's original duration weakness is separate, not manually overridden.

### Validation and evidence
- 489 Python regressions passed, including exact XI/marginals, false nine, hard caps, slot/window limits, own-goal clean sheets/BPS, goal-budget conservation, floating interval boundary, disabled-candidate draw-for-draw equivalence, atomic capture and cutoff/exposure regressions.
- Classic manager/profile/deadline JavaScript checks passed; all 4,002 current baseline outputs remain exact.
- Original 26,159-row historical reference and TS replay preserved: 2,125 points, 44 transfers, 28 hit points.
- [Final code A/B workflow](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38375971604): passed at 62374a7.
- [Full audit](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38375971613): passed at 62374a7.
- [Detailed mathematics, all ablations and limitations](https://github.com/pdamkier-del/fpl-analytics-app/blob/model-audit-optimization-20261012/docs/audits/2026-10-13-simulator-correctness.md).

Simulator-correctness evidence checkpoint: fa90ad4c1d9daef4d52e91d58c2f44b617e3e34f. Remains draft, with no production promotion. Historical marginal projection can be large (+62.394 percentage points for an inconsistent keeper partition). Starting-XI validity does not certify continuous 990-minute team coverage. Source publication/roster/price/schedule gaps and missing historical six-GW future cells block full-chain certification and a defensible candidate six-GW TS comparison. No private manager-state or purchase prices were used or published.

### Completed minute-model component and PM research
Frozen production MM/PM/vFinal/TS/chips remain unchanged. The isolated candidate includes cutoff-only prefix features, regularized and player/team-intercept start models, empirical all-cause departure hazards, a full starter-duration distribution sampler, a structural hard-availability ablation and a score-scenario hazard screen. Selection: 2024 GW11–21; later temporal evaluation: 2024 GW22–38 and 2025 GW6–38. The seasons were previously used in baseline development, so these are not pristine independent model-development holdouts.

**Haaland's 68.301824 xMins are exactly explained:** P(start)=0.8382304242, conditional starter mean=80.2773039531, bench appearance=0.4207609277, bench minutes=14.8523640260. The original 0.321926-match duration half-life gives his latest 79-minute start 88.39% of the duration weight. No individual override or assumed substitution cause is used. Start selection receives ~70% of 2025 minute-error MAE attribution; the allocation is descriptive, not causal.

**Completed original-component PM replay**, 330 fixtures/season, 400 draws per mode, original seeds and exact original references:

| Test cohort | Original xP MAE / RMSE | Selected start + full survival distribution | Paired MAE delta, fixture-block 95% CI |
| --- | --- | --- | --- |
| 2024 GW22–38, 13,105 rows | 0.947794 / 1.848146 | 0.932798 / 1.842353 | −0.014996 [−0.018565, −0.011477] |
| 2025 GW6–38, 26,159 rows | 0.929173 / 1.880707 | 0.923462 / 1.866162 | −0.005711 [−0.008661, −0.002788] |

Played-player point MAE/RMSE also improve in both cohorts. But raw analytic minute MAE still deteriorates in 2025 (10.533125→10.893571); the late 2025 point-MAE interval alone includes zero. Merely feeding the survival mean to the original Normal sampler worsens point MAE. Distribution shape matters and is not equivalent to changing a minute label. This is the most promising full-PM research candidate, not an approved replacement.

The availability ablation improves all-row 2025 point MAE to 0.918891, but played-player accuracy and three-state log-loss worsen slightly. There are 19 OUT/actual-minute source contradictions. The archived suspended-state composition defect (135 rows, mean 6.358 xMins despite zero actual minutes) is confirmed; an already-existing live eligibility gate must not be confused with the archived MM path. Score-context improves minute RMSE but worsens MAE in both seasons; its full PM/TS effect remains Not Available.

- [Completed full MM/PM/context workflow](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38565961308): success at 892fad1, including 505 regression tests at that code.
- [Full production/reference audit](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38565961258): success at 892fad1.
- [Report recovery](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38711276013): original artifact report SHA256 values verified; complete PM/component/calibration reports are now committed.
- Atomic validated gzip CSV/JSONL checkpoints preserve previous complete results after interrupted writes; no model mathematics changed.
- [Detailed Danish report](https://github.com/pdamkier-del/fpl-analytics-app/blob/model-audit-optimization-20261012/docs/audits/2026-10-14-minute-model-research.md).

The original TS remains 2,125 / 44 transfers / 28 hit points. Missing historical six-GW future cells prevent a defensible new candidate season-total TS test. Actual source publication times, roster/medical coverage, independent holdout and combined simulator/MM acceptance remain blockers. No private manager-state or production deployment. `locked_model_active=false`.

### Verified frozen-current MM → full PM focus, 15 October
[Current focus workflow](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38712316437) passed at 3838f83. Same frozen cutoff 2026-10-12T10:45:27.093744+00:00, three complete club fixtures, eight paired 400-draw seeds. Every original component rebuild matches within 1e-10; the published first-seed original xP matches exactly for every player in those fixtures.

| Player | Original / candidate input P(start) | Original / candidate simulated minutes | Original / candidate mean xP |
| --- | --- | --- | --- |
| Haaland | 83.8230% / 82.9398% | 67.66969 / 70.84969 | 5.68156 / 5.66687 |
| Saka | 95.4422% / 93.4392% | 81.79781 / 79.13031 | 5.57219 / 5.44594 |

Candidate is selected start + full survival distribution, not the earlier simulator-correctness candidate. Seed rule: 93000000 + offset among all 60 frozen fixtures + repeat*100000. These means must not be mixed with a single published draw-budget or the earlier seed grid. They are scenario outputs, not observed future accuracy. Chelsea's total GW7 goal intensity remains exactly 1.342868819888325. All Saka point components, both players' seed SDs, input checks and provenance are in the committed report.

**Final local regressions: 510 passed**, plus Classic Manager, player-profile snapshot and forecast/deadline JS checks. [Full audit at f8bd1f9](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38711275817) passed; later audit runs on subsequent research/docs commits are separate and must not be reported as passed before completion. Latest evidence commit: [75e6ad9](https://github.com/pdamkier-del/fpl-analytics-app/commit/75e6ad96e12a7105a46f4b693624760e68f4fa08). Remains draft. No production replacement or live-certification; locked_model_active=false.

### 15 October: completed isolated goal/assist PM research

**Decision: retain the locked original PM/vFinal. No production promotion.** The complete two-season ablations are now saved in [adf948f](https://github.com/pdamkier-del/fpl-analytics-app/commit/adf948fc805a4816d3f04a48db09107e7c5446f2), with five byte-for-byte source reports, verified SHA-256 manifest, extra group/team calibration and the [full audit, mathematics and results](https://github.com/pdamkier-del/fpl-analytics-app/blob/adf948fc805a4816d3f04a48db09107e7c5446f2/docs/audits/2026-10-15-goal-assist-model-research.md).

All six jobs in [primary PM workflow 38717540912](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38717540912) passed: development selection, four historical season/MM arms and frozen-current diagnostics. Each historical arm replays 330 fixtures at 400 draws. The two locked-MM arms reproduce their original xP references exactly; experimental-MM arms use their own unchanged-PM reference and intentionally do not claim equality to old-MM outputs. Hyperparameters were selected only on 2024/25 GW6–21 before later target forecasts were read.

| PM under locked MM | 2024/25 GW22–38 xP-MAE | 2025/26 GW6–38 xP-MAE |
| --- | ---: | ---: |
| Original | 0.9477938 | 0.9291727 |
| Finishing only | 0.9473298 | 0.9289755 |
| Assist conversion | 0.9476272 | 0.9285983 |
| Finishing + assist | 0.9471705 | 0.9284534 |
| Hierarchical EB | 0.9469332 | 0.9285890 |
| Hierarchy + joint | 0.9469365 | 0.9287732 |
| Changed team intensity | 0.9510572 | 0.9289046 |

Assist-only improves assist binary log-loss in both seasons; its point-MAE delta is −0.0001665 [−0.0008321,+0.0004844] in 2024 and −0.0005744 [−0.0009725,−0.0001684] in 2025 (paired fixture-bootstrap 95% CI). The 2024 point effect is uncertain, subgroup/BPS results are mixed, and these reused seasons are not untouched whole-model holdouts. Combined PM does not reliably improve the experimental-MM reference in either season. Changed team intensity clearly worsens 2024 point-MAE: +0.0032634 [+0.0007330,+0.0058521]. Do not promote it merely because it raises Chelsea's forecast. More complex joint/hierarchy variants do not establish a robust overall FPL gain.

**Frozen 12 October diagnostic, not a new live forecast:** eight paired seeds × 400 draws. Haaland original/combined xP 5.68156 → 5.63031; Saka 5.57219 → 5.56531. Haaland minutes stay 67.6697 in both PM arms; separately selected experimental MM gives 70.8497. Chelsea lambda is 1.34286882 fixed versus 1.39585108 in the rejected adjusted-total candidate. All ten point components and paired seed SDs are reported. Monte Carlo SD is distinct from historical sampling uncertainty.

Audit confirms the actual rolling team model fits xG alone; ordinary goal/assist events are already shared. All-xG conversion is not identified non-penalty finishing, and FPL-assist/xA is not pure creativity. Added opt-in Gamma-Poisson player conversion, league→season-team→player shrinkage, xG/xA ablation, fixed/adjusted ordinary-goal budgets and self-excluding maximum-entropy assist marginals. Penalty/scoring/BPS coefficients remain original. Existing XI/own-goal/special-assist limitations are retained in this controlled PM matrix; prior opt-in simulator corrections remain separate.

Verified raw 2024 shotmaps supply native non-penalty information within that provider, but 183 xG rows differ by more than .05 from Core, preventing unverified cross-provider subtraction. The one Wissa goal-credit discrepancy is explained by an official later appeal with unchanged finalized FPL points. Historical actual publication times, multi-season compatible non-penalty inputs and creator links for failed shots remain incomplete. Chelsea GW6 is provisional in the frozen manifest. No new values or event labels were invented.

**Tests:** 519 local Python tests passed (21.76s), including nine focused conversion regressions. [Full audit 38720239913](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38720239913) passed at 7c16891; [extra calibration/evidence export 38720669600](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38720669600) passed at 9c7ecbb. Export checkout ordering was fixed without changing numerical code. [Full audit 38720669527](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38720669527) also passed at 9c7ecbb. Full reports and hashes are committed, so evidence no longer depends only on expiring artifacts. The automatic audit for final evidence/docs-only commit adf948f is [38721956714](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38721956714); it was still running at the final check and is not counted as passed here.

**TS/certification limits:** only 33/183 audited historical future-horizon cells exist; no candidate 2,125-point TS replay is claimed. Preserve original 2,125 / 44 transfers / 28 hit points. Source/publication and BPS/MM requirements remain blockers. Assist-only is a research candidate for a new independent period, not a production replacement. No private manager data used, no app deploy or merge. Production math unchanged; **locked_model_active=false**, promotion_allowed=false.

### 15 October: completed player-first PM v2 — phases A/B

**Implemented and tested; do not promote this version.** The candidate is a genuine lineup-dependent player model: regularized player xG90/xA90 and finishing profiles determine ordinary team chance production and event timing as players start, leave and enter the pitch. The original simulator's scoring, penalties, BPS, clean sheets and defensive components are reused. Simple, hierarchical and hybrid models are isolated from production.

[Final report and mathematics](https://github.com/pdamkier-del/fpl-analytics-app/blob/0e1117da55662b567bba23688f79b760ad5b3d42/docs/audits/2026-10-15-player-pm-v2.md) · [evidence and original hashes](https://github.com/pdamkier-del/fpl-analytics-app/tree/0e1117da55662b567bba23688f79b760ad5b3d42/analysis/results/player-pm-v2-20261015) · [checkpoint](https://github.com/pdamkier-del/fpl-analytics-app/blob/0e1117da55662b567bba23688f79b760ad5b3d42/docs/checkpoints/2026-10-15-player-pm-v2-completed.md). Final evidence commit: [0e1117d](https://github.com/pdamkier-del/fpl-analytics-app/commit/0e1117da55662b567bba23688f79b760ad5b3d42).

Development selection (2024/25 GW6–21) chose half365/strength5 profiles and hybrid h=.25, beta=.25: 75% player production, 25% original team anchor, plus an aggregate creative elasticity. This is not an actual-goals/xG blend and not learned specific player-pair chemistry. Selection was persisted before later forecasts were read.

| Locked MM, PM candidate | 2024/25 GW22–38 MAE / RMSE | 2025/26 GW6–38 MAE / RMSE |
| --- | ---: | ---: |
| Original | .9477938 / 1.8481456 | .9291727 / 1.8807071 |
| Simple player | .9521089 / 1.8482696 | .9307590 / 1.8788192 |
| Hierarchical | .9518323 / 1.8485853 | .9298982 / 1.8777768 |
| Hybrid | .9495469 / 1.8439380 | .9295283 / 1.8785701 |

Hybrid point-MAE Δ95% CIs: 2024 +.0017531 [−.0025199,+.0057131]; 2025 +.0003556 [−.0023604,+.0031562]. RMSE improves under locked MM, so the result is a tradeoff rather than a universal failure; MSE is a relevant loss for conditional means. It is not sufficient for production approval. Hierarchical assist binary log-loss improves both seasons with paired intervals below zero. Team-goal/xG metrics improve slightly for hybrid but hold-goal MAE intervals include zero. Reused periods are not pristine whole-model holdouts.

**MM interaction is negative:** under the same experimental start/survival MM, original PM → hybrid point-MAE is .9327982 → .9331038 (2024, uncertain), and .9234618 → .9269759 (2025), Δ+.0035141 [.0006973,.0062338]. 2025 RMSE also worsens. Scarce-history/reserve and club-transition results do not establish robust gains.

**Error attribution and alternatives:** exact Shapley decomposition of paired point-MAE shows 2024 hybrid goal/assist improvements −.0015762/−.0014790 offset by clean-sheet contribution +.0045944. Under experimental MM 2025, goal/assist deterioration dominates instead. This is algebraic error attribution, not causality. An analytic finishing-off ablation helps 2024 but hurts 2025; no full xP improvement is claimed. A 1,000-lineup check on two fixtures per season confirms a Jensen no-goal shift and existing independent-XI physics: only 19.6–25.5% exactly 11 starters, 35.3–41.8% over 11 in those eight team/fixture cases. Next priority is a controlled original-PM/player-PM comparison under the already existing legal joint-XI candidate; no production sampler is changed here.

**Frozen 12 October focus, eight paired 400-draw seeds (not new live data):**

| Player | Original xP | Hybrid xP |
| --- | ---: | ---: |
| Haaland | 5.68156 | 5.62281 |
| Palmer | 3.86313 | 4.88562 |
| João Pedro | 3.35500 | 3.25594 |
| Saka | 5.57219 | 5.21344 |

Chelsea original goal intensity 1.34286882 → hybrid xG 1.39228783 / goals 1.43465631. No manual boosts. All ten point components, seeds, conditional profile intervals and action/role supplements are reported. Minute inputs are unchanged; small differences in simulated minute means arise from changed RNG consumption. GW6 Chelsea source remains provisional.

**Verified runs:** [primary matrix 38729720330](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38729720330), all 18 jobs; [focus/export 38730402769](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38730402769); [mechanisms/regressions 38766320676](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38766320676), **532 tests passed in 22.58s**; [full audit 38766116114](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38766116114) at ed27477. Historical matrix totals 1,584,000 match draws. Nine original report SHA-256 values verified; two locked-MM baselines reproduce exactly, and each experimental-MM comparison has its own unchanged-PM reference. The subsequent final docs/evidence commit's automatic audit is separate and is not counted as passed in advance.

**Remaining limits:** actual publication clocks, complete multi-season compatible npxG/creator links, temporal tactical/set-piece roles, summer-club identity bridge, independent validation and joint-XI interaction. The verified current 1,204-row action ledger is a separate supplement, not silently introduced as historical evidence. Only 33/183 historical future-horizon cells are available, so no candidate TS season total is fabricated. Original 2125 / 44 transfers / 28 hit points, production math, TS and chips remain unchanged. No private manager data, merge or deploy. **locked_model_active=false; promotion_allowed=false.**

## Dynamic reliability PM v2 — 15 October

**Implemented and historically replayed; do not promote dynamic weights.** Numerical code `72b61e4`; reliability/audit code `9fac2d1`. Isolated additive experiments preserve all preexisting tracked files at `0e1117d` (60 existing source files checked byte-for-byte). Production MM/PM/TS/chips, 2125 / 44 transfers / 28 hit points and `locked_model_active=false` remain unchanged.

18 development configurations compare fixed75, history-amount and individual-contribution-weighted reliability, conditional profile variance, correlated-error moments and regularized/hierarchical logistic gates. Training labels must be known strictly before cutoff. Development selected **xG-contribution-weighted n/(n+20)**, validation xG deviance .34586850 vs fixed .34786894 (0.575% selected gain). No target XI/minutes/results determine weights; no player-specific adjustments. Conditional variances are not assumed to be full predictive variances, and covariance is not assumed zero.

**Completed controlled matrix:** [38772814007](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38772814007), all38 jobs passed; 36 replays, 24 model/season cells, 3,168,000 match draws. Two seasons × locked-MM independent/legal XI plus experimental-MM legal XI. Existing legal sampler gives11 starters/oneGK, consistent availability and nonoverlapping slots. Both PMs retain identical legacy OG/CS/scoring semantics. XI effects are separated from gate effects. Original independent references reproduce exactly; fixed75 reproduces prior candidate; point components reconcile.

| Locked MM, legal XI | 2024 point-MAE | 2024 RMSE | 2025 point-MAE | 2025 RMSE |
| --- | ---: | ---: | ---: | ---: |
| Original PM | .94690424 | 1.85013908 | .92630070 | 1.87924161 |
| Fixed75 PMv2 | .94626021 | 1.84909827 | .92519343 | 1.87765765 |
| Selected dynamic | .94720527 | 1.85023194 | .92645657 | 1.88002554 |
| Uncertainty gate | .94615166 | 1.84725583 | .92481163 | 1.87800108 |

Selected dynamic ΔMAE vs fixed: **2024 +.0009451 [−.0017523,+.0035498]; 2025 +.0012631 [−.0005395,+.0032254]**. Uncertainty gate's tiny MAE gains also have intervals crossing zero; 2025 RMSE worsens. Learned/covariance gates do not establish gains. Experimental-MM interaction reverses sign across seasons. Independent-XI amount gains do not survive legal-XI controls. Do not retrospectively promote the gate that looks best on reused evaluation.

XI correction itself improves fixed75 MAE .94954693→.94626021 (2024), .92952827→.92519343 (2025). Maximum raw→feasible individual start-probability shift reaches22.05pp/62.39pp in locked MM; legal probabilities are identical **within** PM comparisons, not falsely claimed identical to infeasible raw marginals. This is a separate MM/input diagnostic.

[Full model audit38774188180](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38774188180) passed **546 tests**, existing reproductions and benchmark preservation. [Reliability/seed evidence38774188162](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38774188162) **passed** at9fac2d1: 86,400 extra draws, source/training cutoff checks, covariance and exact error attribution. [Corrected cohort export38777082642](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38777082642) **passed** at140387a, reusing simulations unchanged. Any-new/absence flags initially saturated due to fringe-player mass; reporting now uses development-median fractions and sparse-group warnings. No gate or forecast changed. Final local suite **547 passed in31.07s**. All11 final report hashes verified byte-for-byte.

Report: `docs/audits/2026-10-15-dynamic-pm-v2.md`. Raw captures/results are public research match data, not private manager state. Limits remain actual publication clocks, verified medical/tactical/summer-transfer labels, reused seasons, legacy scoring physics, raw artifact retention and incomplete six-GW TS inputs. No candidate TS total, merge, deploy or live certification.


**Final durable evidence:** [32c2338](https://github.com/pdamkier-del/fpl-analytics-app/commit/32c23387481667f81c7cf67cb2326993740487f4) · [complete mathematics/results](https://github.com/pdamkier-del/fpl-analytics-app/blob/32c23387481667f81c7cf67cb2326993740487f4/docs/audits/2026-10-15-dynamic-pm-v2.md) · [full reports/manifest](https://github.com/pdamkier-del/fpl-analytics-app/tree/32c23387481667f81c7cf67cb2326993740487f4/analysis/results/dynamic-pm-v2-20261015) · [resume checkpoint](https://github.com/pdamkier-del/fpl-analytics-app/blob/32c23387481667f81c7cf67cb2326993740487f4/docs/checkpoints/2026-10-15-dynamic-pm-v2-completed.md).

Endpoint residual correlations are .973/.977. Conditional profile variance is only one part of total forecast error, not a full predictive uncertainty estimate; its residual-MSE ratio is not latent credible-interval coverage. Current legal-XI amount's goal/assist point-error terms worsen while CS offsets part of the loss, unlike the earlier independent-XI explanation. Exact Shapley attribution is descriptive, not causal. Six-seed small-fixture checks show material MC dispersion. Analytic raw-MM-exposure gate fitting does not prove optimal weights under projected legal-XI exposures; a new legal-exposure-trained gate needs predeclared selection and fresh validation.

**Decision:** no tested dynamic gate establishes robust superiority over both original PM and fixed75. Retain fixed75 research reference and unchanged original production. Legal-XI correction itself is more promising: fixed75 point-MAE deltas vs independent XI are −.0032867 [−.0059752,−.0005329] / −.0043348 [−.0064609,−.0021631], still reused research periods rather than production certification. Raw-source retention and full six-GW historical gaps remain explicit. Later automatic audits on reporting/evidence-only commits are separate from the verified green numerical/audit runs above.

