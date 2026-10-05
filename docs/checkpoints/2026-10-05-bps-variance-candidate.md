# BPS variance calibration — selected candidate

The selected BPS conditional mean from the prior experiment is unchanged:
soft role + recent detailed background actions, half-life 3, L2=200.

This step calibrated only the residual uncertainty used inside match-level BPS
ranking. Variance was fit on GW16-21, matching the simulator scaling:
background_total ~ Normal(rate90 * minutes/90, sd90 * sqrt(minutes/90)).

Development residual NLL:
- global sd90: 2.68869
- position-specific shrunk sd90: 2.66342 -> selected

Selected shrunk sd90:
- GK 3.293
- DEF 4.563
- MID 5.116
- FWD 4.275
Global reference sd90 4.662.

Reused GW22-38 joint diagnostic, 144 fixtures / 11,794 rows, 360 draws:
Bonus deterministic-mean vs variance-calibrated:
- log loss 0.19462 -> 0.18134
- Brier 0.07191 -> 0.07164
- expected bonus MAE 0.13639 -> 0.13501
- expected bonus RMSE 0.40319 -> 0.40217
- mean predicted bonus 0.08062 -> 0.07804 vs actual 0.07792
- P(any bonus) 0.03994 -> 0.03880 vs actual 0.03900

Total xP:
- MAE 0.92273 -> 0.92129
- RMSE 1.84881 -> 1.84661
- bias +0.02707 -> +0.02325

All key reused-diagnostic metrics improve after variance calibration, including
the log-loss/RMSE weaknesses from the previous mean-only BPS candidate.

This remains a reused diagnostic, not an independent holdout, so no production
promotion is declared. For the integrated 2026/27 candidate, retain the selected
background mean/variance architecture but score generated BPS using 2026/27
official rules.

Artifacts:
analysis/results/bps-variance-calibration-20261005-v1/
