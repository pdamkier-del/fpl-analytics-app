# Shot-level finishing feasibility protocol

Question: can existing shotmaps identify a reproducible conditional conversion model beyond a goals/xG aggregate? This is a provider-internal test of P(goal | realized shot xG, shooter history), not a pre-match xP forecast. Future shot volumes/locations are not known before a match.

Use all verified 2024/25 Premier League shotmaps and existing canonical player/fixture identity mappings. Separate penalties and own goals. Require complete native pre-shot xG and unambiguous identity. Quarantine the one previously flagged player/fixture with differing provider/Core goal credit. No post-shot expectedGoalsOnTarget, target placement, save/outcome flags or actual goals become predictors. Player history uses the same provider throughout; do not subtract provider penalty xG from FPL xG.

Models: native xG; a shared logit calibration a+b*logit(xG); that calibration plus a simple historical Gamma conversion factor; a joint shared logit calibration plus a Gaussian-shrunk player log-odds offset. Cold-start offsets are zero. The intercept/slope account for global source calibration before interpreting player differences.

Develop using past shots before each archived GW cutoff. Choose Gamma strength from [5,20,80], player ridge from [1,5,20,80], and recency half-life from [none,90,365] only on GW16–21 log loss. Then freeze those settings and walk forward through GW22–38, refitting from newly known past shots at each cutoff. Do not tune to Saka/Palmer or later evaluation results. Baseline calibration uses the same chosen recency as each candidate. Full data only has one consistent-provider shot season: do not claim multi-season identified finishing skill.

Use archived MM GW cutoff timestamps and Core kickoff+4h availability proxy; require every target match to start after its cutoff, and every training match to be known before it. Source capture times are not certified historical release times. Evaluate Bernoulli log loss, Brier score, calibration, goal-count bias, shot-type groups and match-paired bootstrap intervals. Count/inspect missing fields, penalties, own goals and source disputes. Do not conflate a correctly fitted conditional conversion model with a validated future-point model.

No production/B-preview/model/manager-state changes. Preserve source hashes, the shot table, validation selection and held-out predictions. If the new model fails to improve, retain native/shared calibration and report feasibility separately from accuracy.

Secondary checks added after the primary results: reinclude the previously flagged four GW9 training shots with frozen hyperparameters, and evaluate a locally discovered later 2026/27 partial shot sample with settings frozen from the original development selection. These are robustness/out-of-time checks, not new tuning or pre-registered primary tests. The later fit uses only the available 2024/25 season and explicitly reports the missing intervening season.
