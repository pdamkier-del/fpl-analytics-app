# Shot-level finishing: feasible, implemented and evaluated

**Yes: the existing source supports a real shot-level experiment.** A native non-penalty shot table, a shrunk individual log-odds model, chronological selection/evaluation and a later-season check are now implemented. No production or B-preview model is changed: the individual model does not establish a stable improvement over the strongest simple baseline.

## Source and identity feasibility

The 2024/25 Premier League archive contains 380 matches and 9,883 shots, all with provider player IDs and shot types. Excluding 33 own-goal entries and 83 penalties leaves **9,767 native non-penalty shots by 457 players**, with complete valid pre-shot xG and canonical player/fixture mapping. The 29 missing xG values in the full archive belong to excluded own-goal entries; no missing non-penalty xG is zero-filled.

Left/right foot, headers and other body-part types are available. The source also contains post-shot xGOT and placement/outcome fields. Those are not predictors: they describe information from the shot's execution/result. The model receives only pre-shot xG and historical player identity; target goal is the binary label. A regression proves that adding outcome-derived xGOT/placement columns cannot change the fit.

The existing cross-source audit flags Yoane Wissa's GW9 player/fixture goal credit (provider two versus Core one). The four corresponding non-penalty shots are quarantined in the primary training table. A secondary check includes them with frozen settings; the conclusion is unchanged. This is a provider-internal goal test, not an assertion of official FPL-goal equivalence.

Only one complete same-provider shot season is restored. A later archived capture from 18 October 2026 supplies another **69 PL matches, 1,904 total shots and 1,885 eligible non-penalty shots**. That is partial current-season coverage, not a second complete season. No 2025/26 shot season is available in this restored source set.

## Model and temporal test

Unlike the previous Gamma ratio, the individual model fits each shot as Bernoulli:

`logit(P(goal)) = shared intercept + shared slope × logit(pre-shot xG) + player offset`.

Player offsets receive a Gaussian/ridge prior toward zero; unseen players have zero offset. Global calibration is fitted separately to avoid attributing all source miscalibration to players. A positive player offset increases the conversion odds for the same shot quality; it is not a uniform fixed addition to xG. Shot-type metrics are reported, but separate player-by-body-part ability is not claimed.

Development uses GW16–21, with training only on shots known before each archived GW cutoff. Ridge choices [1,5,20,80], Gamma strengths [5,20,80] and recency half-lives [none,90,365 days] are selected only there. Selected settings: **no recency decay; player ridge 5; Gamma strength 20**. Hyperparameters are saved before evaluation. Evaluation then walks forward through GW22–38 with fixed settings, updating player estimates only from newly known past matches. Source availability inherits the documented kickoff+4h proxy, not certified actual release clocks.

The comparison includes native xG, shared calibration, an aggregate Gamma-style residual conversion factor and the individual shot model. For fairness, aggregate factors use the shared curve's expected-goal exposure; all baselines with matching recency are retained. This is conditional `P(goal | observed shot xG)`: target chance quality is conditioned on, not invented as a known pre-match feature.

## Primary results: 4,255 later non-penalty shots, 445 goals

Lower log loss and Brier score are better.

| Model | Log loss | Brier | Expected goals |
| --- | ---: | ---: | ---: |
| Native pre-shot xG | **0.270433** | **0.076544** | 443.70 |
| Shared calibration | 0.270705 | 0.076617 | 432.31 |
| Aggregate conversion | 0.271077 | 0.076719 | 437.48 |
| Individual shot model | 0.272822 | 0.077142 | 435.41 |

Individual versus native log-loss delta is **+0.002388**, match-paired 95% bootstrap interval **[+0.000659,+0.004242]**. Versus the matching shared calibration it is +0.002117, interval [+0.000545,+0.003769]. This particular individual model worsens prediction in this evaluation period. Including the disputed GW9 training shots changes individual log loss only to 0.272825; evaluation remains the same 4,255 shots.

## Additional later-season check: 1,885 shots, 183 goals

This secondary check was added after finding newer local source coverage. No parameters were retuned on it. Train on the available 2024/25 non-penalty shots, freeze before 1 August 2026, and evaluate the available 2026/27 shots from 69 matches. The intervening 2025/26 shot season is absent. Known stable provider IDs bridge to canonical identities; unseen players retain neutral offsets. The report separately counts identity bridges and players with actual training shots.

| Model | Log loss | Brier | Expected goals |
| --- | ---: | ---: | ---: |
| Native pre-shot xG | 0.271095 | 0.076501 | 199.88 |
| Shared calibration | **0.269699** | **0.075971** | 194.47 |
| Aggregate conversion | 0.279694 | 0.076316 | 195.32 |
| Individual shot model | 0.270344 | 0.076368 | 191.31 |

The individual model improves versus native xG by -0.000751 log loss, but its interval [-0.003382,+0.001907] includes zero. Shared calibration is stronger here. Different metrics can disagree: the aggregate factor has a slightly lower Brier score than the individual model but worse log loss. All score/probability predictions and paired intervals are retained rather than selecting a favorable metric.

## Interpretation and limits

- Shot-level modelling is technically feasible, including clean separation of penalties. It is not yet a documented player-finishing upgrade to PM.
- The full-season table has a median of only **14 non-penalty shots per player**; 284/457 players have fewer than 20. Consistent individual conversion is difficult to estimate from that sample. These counts include the flagged rows before primary quarantine.
- Player offsets can absorb unobserved chance context, source bias or temporary conditions. This experiment does not identify a permanent biological skill or account for every goalkeeper/opponent effect. Source calibration may also change over time.
- One full season plus a later partial sample and a missing intervening season do not establish stable multi-season ability. These historical periods have also been inspected in prior model research; no pristine whole-model validation is claimed.
- To use this in pre-match PM, future shot quantity/quality and player exposure must still be forecast and a complete PM/bonus/TS comparison performed. No pre-match xP gain is inferred from realized shot xG.
- Creator links at unsuccessful shots remain absent, so this does not resolve the precise creator→receiver assist hypothesis.

The simpler existing PM remains deployed. The new shot-level data layer and opt-in model are available for reproducible further validation; there is no Saka/Palmer-specific tuning.

## Files and reproduction

- `src/fpl_v1_1_model/experimental_shot_finishing.py`: validated conditional fit, shared calibration and shrunk player offsets.
- `scripts/research_shot_finishing.py`: source/identity audit, temporal selection, primary evaluation and credit sensitivity.
- `scripts/check_shot_finishing_later.py`: frozen-setting later partial-season check.
- `tests/test_experimental_shot_finishing.py`: five tests for shrinkage, cold starts, no future/missing observations, monotonicity and no post-shot predictor leakage.
- `analysis/results/shot-finishing-20261020/`: source hashes, native shot table, selected settings, complete held-out predictions, paired scores/calibration and later/sensitivity reports.

All **738 Python regressions passed**. Primary, credit-sensitivity and later commands completed. App, production model, original simulator and private service files remain unchanged. No private manager data or actual worker job is used.

```bash
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/research_shot_finishing.py \
  --mm-root /tmp/fpl-general-conversion/mm/mm-research-20261014
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/research_shot_finishing.py \
  --mm-root /tmp/fpl-general-conversion/mm/mm-research-20261014 \
  --include-disputed --frozen-selection analysis/results/shot-finishing-20261020/selection.json \
  --out analysis/results/shot-finishing-20261020/credit-sensitivity
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/check_shot_finishing_later.py
```
