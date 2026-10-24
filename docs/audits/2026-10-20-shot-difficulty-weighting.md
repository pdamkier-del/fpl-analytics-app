# Do difficult goals receive more finishing credit?

**Yes, in the existing shot-level prototype.** A fixed-history controlled fit confirms the effect. Stronger difficulty weighting was also tested on real shots. It modestly improves the previous individual prototype, but does not establish a consistent improvement over the strongest simple reference. A player-specific difficulty curve does not help after matching regularization. Neither is enabled in PM or the public app.

## Actual existing learning rule and controlled fit

For a Bernoulli player log-odds offset the data score is `goal - predicted_probability`, before adding its shrinkage penalty. With the neutral curve, predicted probability equals pre-shot xG. Goals at low xG therefore produce larger positive score; missed high-xG chances produce larger negative score. The score is a likelihood gradient, not FPL points or an xP multiplier.

To verify actual fitted behavior, keep a player's history identical at 50 shots of 0.10 xG, five goals, a fixed shared calibration curve and ridge prior 5. Add exactly one shot, then solve for the new player offset:

| Added shot | Initial likelihood score | Fitted offset change |
| --- | ---: | ---: |
| Goal, 0.05 xG | +0.95 | +0.097649 |
| Goal, 0.80 xG | +0.20 | +0.020626 |
| Miss, 0.05 xG | −0.05 | −0.005242 |
| Miss, 0.80 xG | −0.80 | −0.084076 |

The difficult goal produces about **4.73 times the upward offset change** in this controlled example. This ratio is not universal; history, calibration and shrinkage affect the final estimate. A single rare goal is not treated as sufficient proof of permanent elite finishing.

## New historical alternatives

Protocol and full numerical report are in `analysis/results/shot-difficulty-20261020/`. This is an exploratory follow-up on already inspected research periods. Hyperparameters are selected only on GW16–21, not on the following test outcomes or named players.

1. **Extra difficulty weight:** apply `clip((0.2/max(xG,0.01))^power,0.5,4)` to all outcomes at each chance quality, normalized to mean one. Goal-only rewards are deliberately avoided: missing the same type of chance must still provide counter-evidence. Development chose power 0.5, player ridge 5.
2. **Individual chance-quality response:** `logit(p)=a+b*exp(-v_player)*logit(xG)+u_player`. The response remains increasing in chance quality. `u` is general finishing; `v` allows relatively stronger difficult-chance conversion. Development chose offset ridge 20, response ridge 80. Both effects shrink toward the shared curve.

The original/native/shared references are retained exactly from the preceding study. Each new model also gets a constant-offset control with the **same selected offset ridge**. These matched controls prevent attributing a gain from stronger regularization to a new difficulty mechanism. They were added after the first pilot results as an attribution check, without new tuning.

Use the same native non-penalty table, quarantined credit discrepancy, original cutoffs and publication proxies. Evaluate **4,255 later 2024/25 shots**, then a frozen all-2024/25 fit on the existing **1,885-shot later partial 2026/27 sample**. No intervening 2025/26 shot season is available.

## Results

Unweighted Bernoulli log loss, lower is better:

| Model | 2024/25 later window | Later 2026/27 sample |
| --- | ---: | ---: |
| Native xG | **0.270433** | 0.271095 |
| Shared calibration | 0.270705 | 0.269699 |
| Existing individual offset, ridge 5 | 0.272822 | 0.270344 |
| Extra difficulty weight | 0.272522 | **0.269548** |
| Individual quality response | 0.271784 | 0.269702 |
| Matched constant offset for quality response, ridge 20 | 0.271111 | 0.269686 |

Extra weighting improves versus the existing individual prototype in both periods. The paired deltas are **−0.000300** (95% interval **[−0.001012,+0.000409]**) and **−0.000797** (**[−0.001667,+0.000082]**). Both intervals include zero. It still worsens versus native xG/shared calibration in the earlier period. In the later sample its small log-loss gain over shared calibration is also uncertain, and its Brier score is worse than shared calibration. Do not pick only the favorable reference, period or metric.

The individual quality-response model improves versus the original ridge-5 prototype but **worsens versus a matched ridge-20 constant-offset model**: +0.000673 log loss in the earlier window (interval [+0.000131,+0.001215]), and +0.000016 in the later sample (interval includes zero). Its apparent gain over the original prototype cannot be credited to a useful new difficulty curve.

## Decision and scope

The user's proposed direction is already present in the basic Bernoulli likelihood, and its actual effect is verified. More aggressive difficulty weighting is a weak research signal, not a documented PM upgrade. Keep current PM and the public B preview unchanged. The new offline variants and predictions are retained for reproducibility.

These tests condition on the realized pre-shot xG. They do not establish better pre-match chance volume, goal means, bonus or full PM/TS performance. Existing single-season/small-player-sample, later coverage, source calibration and missing creator-link limitations continue to apply. Selection on earlier rounds is temporally controlled; these reused research periods are not pristine whole-model validation.

Code: `experimental_shot_difficulty.py`, `research_shot_difficulty.py`, and four targeted tests. All **742 Python regressions passed**. Existing shot-model source and prior reports are unchanged; no production source is edited. Evidence hashes bind the new code/results and reused source tables.

```bash
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/research_shot_difficulty.py \
  --mm-root /tmp/fpl-general-conversion/mm/mm-research-20261014
```
