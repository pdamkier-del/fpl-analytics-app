# GK shot-quality / save-efficiency experiment — rejected

A richer goalkeeper experiment tested cutoff-safe shot quality and team save
efficiency on top of the frozen keeper save mean.

Candidate feature families:
- shot quality: attacker xGOT/SOT, xG/SOT, shots/SOT, big chances/SOT plus
  defending xGOT/SOT and xG/SOT allowed
- save efficiency: team saves/SOT faced and an xGOT goals-prevented proxy
- combined quality + efficiency

Half-lives: 6, 13, 20 matches. Ridge penalties: 10, 50, 200.
Protocol: train GW6-15, select GW16-21, refit GW6-21, reused diagnostic GW22-38.

The numerically best candidate on development was save-efficiency, half-life 20,
L2=200, but it still FAILED the baseline gate:
- development save NLL delta +0.000954 (worse)
- development save-point MAE delta +0.007660 (worse)
- development save-point RMSE delta +0.004377 (worse)

Therefore no candidate is promoted.

On reused GW22-38 the same candidate improved keeper-only count metrics by tiny
amounts:
- save NLL 2.035816 -> 2.033101
- save MAE 1.483546 -> 1.479716
- save RMSE 1.920708 -> 1.917448
- save-point MAE 0.582870 -> 0.582502
but it worsened joint nonbonus xP:
- MAE 0.822704 -> 0.823510
- RMSE 1.576366 -> 1.577718

It also moved mean predicted saves slightly farther from the actual level:
2.74086 -> 2.73485 vs actual 2.87941.

Interpretation:
- simple recency, threshold calibration, and richer team-level xGOT/shot-quality
  / save-efficiency residuals have all failed to produce a robust GK improvement;
- retain the frozen keeper baseline for the integrated candidate;
- do not add a constant save multiplier;
- any later GK research should likely be individual-keeper identity/skill or
  richer shot-level information, but this is lower priority than finishing the
  remaining point components.

Artifacts:
analysis/results/gk-shot-quality-efficiency-20261005-v1/
