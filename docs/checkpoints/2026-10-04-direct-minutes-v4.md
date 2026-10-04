# Direct frozen-minute evaluation completed

Continues `0b914e0c42ed92557f550c2f4c39e9639f5d4c36`. The user requested
evaluation of the new minute model itself, not another old-model season run.
No models were fitted, predictions regenerated or transfer/chip policies changed.

The primary cohort is exactly the 144 whole fixtures / 11,794 player-fixture
rows used in the latest control/v4 point diagnostic, GW22–38. Both arms have
identical rows and actuals. All actual starts and minutes match Historical Core
and both original forecast files. All probabilities and expected minutes
match the frozen sources to 1e-12. The selected v4 variant is workload_start,
not workload_decomposition. The 26 blocked whole fixtures remain excluded.

| Metric (lower is better) | Original v2 | Internal role control | Selected v4 |
| --- | ---: | ---: | ---: |
| Expected-minute MAE | 11.969695 | 11.847375 | 11.509261 |
| Expected-minute RMSE | 21.920483 | 21.855003 | 21.573631 |
| Minute bias (predicted minus actual) | +0.039198 | −0.053266 | −0.214522 |
| P(start) Brier | 0.077751 | 0.077267 | 0.075779 |
| P(start) log loss | 0.259617 | 0.253180 | 0.246429 |
| Calibration ECE, ten fixed bins | 0.024988 | 0.015915 | 0.007284 |

Versus original v2, v4 reduces minute MAE by 0.460434 minutes (3.85%),
RMSE by 1.58%, Brier by 2.54% and log loss by 5.08%. Versus the internal
role-only control, minute MAE improves by 0.338115 minutes. These are separate
comparators: internal role_control is not the old joint-simulator control.

Calibration example: the v4 70–80% probability bin has 532 rows, average
predicted probability 75.57%, and actual start rate 75.00%. The 80–90% bin
has 1,254 rows, predicted 85.79%, actual 85.25%. The 50–60% bin is less good:
267 rows, predicted 55.28%, actual 50.19%. Mean P(start) equals the overall
start rate by design because each team is normalized to eleven; that equality
alone is not calibration evidence.

| Actual-outcome diagnostic slice | Rows | v2 minute MAE | v4 minute MAE |
| --- | ---: | ---: | ---: |
| Did not play | 7,444 | 6.590314 | 5.747928 |
| Started | 3,168 | 21.832858 | 21.640168 |
| Came on as substitute | 1,182 | 19.412683 | 20.640091 |

The large no-appearance group contributes much of the overall improvement.
Actual substitutes are worse by 1.227408 minutes. These slices evaluate
unconditional expected total minutes, not conditional starter/cameo duration
forecasts. They are posthoc descriptive; actual outcome labels never enter
the forecasts. Do not conclude that all minute components improved.

MAE improves across all four positions, with smallest gain for forwards
(11.579580 → 11.485299); forwards' P(start) Brier worsens
(0.078901 → 0.080325). MAE improves in 16 of 17 GWs; GW32 worsens by
0.753514 minutes. Large predeadline role-information-change bands are also
slightly worse versus v2, so rotation/role changes are not a resolved weakness.
Their fixed descriptive bands are [0,.01), [.01,.05), [.05,.1), [.1,infinity).

Exploratory paired 2,000 GW-block resamples give the v4−v2 MAE difference
interval [−0.620744, −0.262360] and Brier difference
[−0.003106, −0.000888]. Resampling these 17 reused GWs is not independent
confirmation and does not correct previous model selection or temporal reuse.

Outputs: `analysis/results/direct-minutes-v4-diagnostic-v1/`: overall and
group metrics, fixed-bin calibration, lossless checksum-verified evaluated
rows, provenance manifest and verification. 107 saved-output/source/metric/
partition/policy checks pass. Target Core values were additionally checked
during generation. Existing models and policy code remain unchanged.

The direct metrics were already available on the broader saved v4 diagnostic
dataset; the previous conversational claim that they had not been evaluated
was too strong. This checkpoint verifies and assembles the exact shared
point-diagnostic cohort, distinguishes the two controls and exposes weaknesses.

Conclusion: v4 improves minutes and starts overall on this reused verified
cohort, but substitute/forward/large-role-change weaknesses remain. This is
not a new holdout, full-season v4 replay or proof of improved season points.
The incomplete official-competition history and inherited v2 GW-order timing
limitations remain. No new fitting or tuning was performed to remedy them.
