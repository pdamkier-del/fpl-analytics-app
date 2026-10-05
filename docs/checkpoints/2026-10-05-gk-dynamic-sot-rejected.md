# GK dynamic SOT form experiment — rejected

The short-form goalkeeper SOT experiment tested whether recent team attack/defence
form should modify the frozen long-run arithmetic SOT opportunity model.

Protocol:
- residual fit GW6-15
- candidate selection GW16-21
- final refit GW6-21
- reused diagnostic GW22-38
- candidate families: fast-vs-slow SOT form, and SOT+xG form
- fast half-lives: 3, 6, 9 matches

Important result: every dynamic candidate was worse than the frozen baseline on
the primary development save-count likelihood. The numerically least-bad
candidate was SOT-only, fast half-life 3, L2=50, but its development save NLL
was still +0.02158 worse than baseline and save-point MAE +0.01214 worse.
Therefore the dynamic recency residual is REJECTED and must not be promoted.

On the reused GW22-38 diagnostic the least-bad candidate had:
- save NLL 2.03750 vs baseline 2.03582 (worse)
- save MAE 1.48019 vs 1.48355 (tiny better)
- save RMSE 1.92202 vs 1.92071 (worse)
- predicted saves 2.72790 vs actual 2.87941, compared with baseline 2.74086
- predicted save points 0.57588 vs actual 0.62353, compared with baseline 0.58012

A marginal joint simulation showed a small apparent nonbonus xP improvement
(MAE -0.00170, RMSE -0.00172), but this conflicts with the predeclared component
selection metric and occurs on a reused diagnostic. It is not evidence for
promotion.

Interpretation:
- simple fast-vs-slow recency in SOT/xG is not the missing goalkeeper signal;
- the frozen long-run arithmetic SOT model should remain the goalkeeper baseline;
- do not add a constant lambda multiplier or a fixed save-bucket correction;
- next goalkeeper research should target richer opportunity/shot-quality
  information (e.g. total shots, SOT, xGOT/shot quality, and possibly
  keeper/team save efficiency) with cutoff-safe features, rather than merely
  shortening recency half-lives.

Artifacts:
analysis/results/gk-dynamic-sot-form-20261005-v1/
