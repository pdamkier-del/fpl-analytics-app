# Joint substitution research candidate

Offline only; no existing entry point or deployment imports this module.

The hierarchical law draws a team substitution count, samples incoming and
outgoing players without replacement, then gives each pair one shared exit/entry
time. Window grouping preserves five substitutions, three windows and continuous
10+1 coverage. Original starting-XI weights and the keeper process are retained.
The previous conditional cameo propensity is a soft ranking signal; explicit
predeadline availability caps remain hard bounds.

`src/fpl_v1_1_model/experimental_joint_substitutions.py` takes an existing match
input, supported lineup mixture, explicit availability-cap mapping, fixture ID,
and the fitted model dictionary. `model.json` is required explicitly: there is no
hidden default model or production switch.

Fit with:

    PYTHONPATH=src:scripts python scripts/fit_joint_substitution_research.py \
      --source HISTORICAL_AUDIT_INPUTS.json.gz --out work/joint-substitution-fit

Validation: three structural tests cover clinical caps, legal timelines, identical
paired starting lineups/keeper timelines, and analytic-versus-sampled minutes.
The portable fitting script reproduces the stored model byte-for-byte.

The fitted heads used 2024/25 and 2025/26 data. The evaluation reused reconstructed
2026/27 GW6/7 inputs, 20 matches and 81,920 match draws. It is not an independent
holdout or an exact replay of published current-app forecasts. A deterministic
repeat preserved all first-pass probability and point-mean results while adding
CRPS. Probabilities of participation and 90 minutes and point CRPS improve in
this diagnostic cohort; minute MAE worsens and point-mean improvement is uncertain.

Timing uses reported FPL-minute proxies; exact substitution timestamps, causes,
pair identities and score-dependent mechanisms were not available. Position
pairing is an explicit engineering preference. No claim of those data is made.

Keep offline. No model activation, six-GW transfer/chip validation or new-round
prospective validation is included.
