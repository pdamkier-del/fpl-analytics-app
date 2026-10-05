# DefCon finalist and goalkeeper update direction

## DefCon finalist

The soft-role DefCon count model remains the structural base. Tactical role is
represented by overlapping q(role)-weighted axes rather than a hard formation
bucket.

A second threshold calibration layer was then selected strictly on development
GW16-21 using official FPL thresholds (DEF >=10; MID/FWD >=12). The selected
calibrator is a global Platt mapping of the Negative-Binomial threshold
probability. Position-specific calibration was tested but did not beat the
global calibration.

Development threshold metrics:
- none: log loss 0.119569, Brier 0.038894
- global calibration: log loss 0.115466, Brier 0.037823
- position calibration: log loss 0.115704, Brier 0.037985

The calibrated probability is inverted back to an equivalent NB mean using the
same dispersion alpha, so the existing joint simulator can consume mu_dc
without a special scoring shortcut.

Reused GW22-38 joint diagnostic, 144 fixtures / 11,794 player-fixture rows:
- role baseline nonbonus MAE 0.829077, RMSE 1.577947, bias +0.044960
- final DC candidate MAE 0.822518, RMSE 1.575326, bias +0.031711
- delta MAE -0.006559, RMSE -0.002621, bias -0.013249

This is the strongest downstream DC improvement observed so far, but GW22-38 is
still a reused diagnostic and the candidate is not independently validated.

Primary artifact:
analysis/results/defcon-threshold-finalist-20261005-v1/

## Goalkeeper update direction

Current keeper architecture is two-stage:
1. attacking SOT creation + defending SOT allowance -> source-SOT mean
2. source-SOT mean -> FPL save mean
3. Poisson save count -> FPL floor(saves/3) points

Existing evaluation shows two separate misses:
- source-SOT is low: 4.1118 predicted vs 4.2864 actual
- saves are low: 2.6855 predicted vs 2.8500 actual
- expected save points are low: 0.5623 vs 0.6136 actual

Bucket calibration identifies where the point error lives:
- P(>=3 saves): 0.4956 predicted vs 0.5439 actual, underpredicted
- P(>=6 saves): 0.06360 vs 0.06364, essentially exact
- P(>=9 saves): 0.00308 vs 0.00606, rare and noisy

Therefore do not add a simple constant multiplier to lambda_saves. A uniform
increase would repair the first bucket but risks overpredicting the already
well-calibrated >=6 bucket.

Recommended next GK architecture:
- retain the existing SOT opportunity layer as the baseline;
- add a threshold-aware save distribution/calibration layer targeting P(3+),
  P(6+), P(9+) jointly;
- preferably use a small hurdle/mixture or calibrated count distribution rather
  than a global lambda multiplier;
- preserve coherent goals+saves simulation and keep penalty saves in the shared
  penalty-event model;
- test current-season team attack/defence form as dynamic SOT features before
  changing the selected arithmetic SOT structure.

Independent validation is still required before production promotion.
