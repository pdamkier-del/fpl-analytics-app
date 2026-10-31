# Difficulty weighting investigation

Offline follow-up requested after the initial shot experiment. Historical results have already been inspected: these are exploratory reused periods, not pristine independent validation. No production or B-preview changes.

First verify the existing Bernoulli player-offset score y-p at a fixed neutral xG curve: hard goals give larger positive score, and missed easy chances larger negative score. Also compare the actual penalized player-offset update on an otherwise identical synthetic history, keeping global calibration fixed.

Then compare the existing constant player log-odds offset with two alternatives, using the existing primary same-provider non-penalty shot table (known credit discrepancy quarantined):
- Extra chance-difficulty weighting in training. Weight ALL outcomes at a given xG by clip((.2/max(xG,.01))^power,.5,4), normalize to mean 1; powers .5/1 and player ridge 5/20/80. No goal-only rewards or post-shot predictors.
- Player-specific chance-quality response: logit(p)=a+b*exp(-v_player)*logit(xG)+u_player. Positive v flattens the curve, allowing relatively stronger difficult-chance conversion; u is general finishing. The slope stays positive. Offset ridge 5/20/80; quality-response ridge 5/20/80/320. v bounded [-1,1]. A small sample is shrunk to a common curve.

Use only pre-cutoff history. Keep no-recency setting from the earlier development selection. Select the two new families solely on GW16–21 unweighted log loss, then freeze settings. Evaluate GW22–38 and separately freeze an all-2024/25 fit before August 2026 for the available later partial sample. Reuse the exact same native/shared/original-offset references. Target pre-shot xG is conditioned on; no pre-match xP claim.

Report unweighted log loss, Brier, match-paired intervals and calibration bias. Do not tune to named players or choose a variant from evaluation outcomes. Keep the current PM if improvement is inconsistent. Existing data coverage, source-clock proxies, missing intervening shot season and creator-link limitations still apply.

After the pilot, add constant-offset controls matched to each selected candidate's offset ridge. This is an attribution safeguard, not a new hyperparameter choice: it checks whether improvement over the old ridge-5 reference comes from stronger shrinkage rather than the quality-response mechanism. Earlier model source and reference prediction tables remain unchanged.
