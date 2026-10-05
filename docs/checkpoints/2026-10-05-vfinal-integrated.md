# vFinal integrated candidate

Integrated components:
- combined minute candidate
- soft-role + shared recent-performance goal/assist allocation
- DefCon soft-role count + threshold calibration finalist
- frozen goalkeeper baseline
- frozen yellow/red discipline model
- shared penalty occurrence/taker/conversion/keeper-save model
- BPS role+recent-detail background mean with position-specific residual variance
- 2025/26 BPS rules used only for historical validation; 2026/27 rules remain live target

Reused GW22-38 diagnostic:
144 fixtures / 11,794 player-fixture rows / 400 draws per fixture.

Nonbonus:
- current v4 MAE 0.829269, RMSE 1.577259, bias +0.044974
- vFinal MAE 0.816420, RMSE 1.573609, bias +0.018092
- delta MAE -0.012849
- delta RMSE -0.003649
- delta bias -0.026882

Total xPts including bonus:
- current v4 event-only BPS MAE 0.938995, RMSE 1.849405, bias +0.058912
- vFinal MAE 0.919069, RMSE 1.846165, bias +0.018146
- delta MAE -0.019926
- delta RMSE -0.003240
- delta bias -0.040766

Bonus:
- MAE 0.145340 -> 0.134686
- RMSE 0.405044 -> 0.402653
- Brier 0.072469 -> 0.071710
- log loss 0.183729 -> 0.183716
- mean bonus 0.091859 -> 0.077976 vs actual 0.077921
- P(any bonus) 0.047442 -> 0.038792 vs actual 0.039003

Position nonbonus MAE deltas:
- DEF -0.01819
- MID -0.01506
- FWD -0.00980
- GK +0.00784 (worse nonbonus)
Total xPts MAE improves for all positions, including GK (-0.00794).

GW stability:
vFinal total MAE improves in all GW22-38.
Nonbonus MAE improves in all except GW28 (+0.00057), with GW38 essentially flat.

Known limitation:
The frozen diagnostic candidate does not carry p_own_goal, so the vFinal test
could not inject the already-accepted own-goal hazard. Yellow/red are included.
This slightly understates architecture completeness and must be fixed in the
production adapter before promotion.

Validation status:
This is not independent holdout evidence. GW22-38 has been repeatedly reused
during development. vFinal is the integrated candidate to carry forward, not a
production promotion yet.

Artifacts:
analysis/results/vfinal-integrated-20261005-v1/
