# Player-based PM v2: defensive-contribution research

Based on PM v2 commit `32c2338`; independent of MM work in PR #4.

## Audit finding

Existing DC already has player/role priors, soft tactical-role feature interactions,
recent defensive actions, expected-minute/opponent effects, an NB2 event
distribution, and threshold probability calibration. Relevant existing files:

- `src/fpl_v1_1_model/defcon.py`
- `scripts/run_soft_role_defcon.py`
- `scripts/run_defcon_threshold_finalist.py`

Building another DC count model that duplicates these elements would not
constitute useful additional player individualization.

## Specific new hypothesis

Separate *individual defensive action propensity* from *opportunity to make
defensive actions* (opponent possession/territory, defensive workload):

```
neutral_rate_i = (tau * role_prior + sum_j decay_j * actions_ij) /
                 (tau + sum_j decay_j * minutes_ij/90 * opportunity_ij)
expected_actions_i = neutral_rate_i * xMin_i/90 * opportunity_next
P(DC bonus_i) = NB2_survival(threshold_i - 1, expected_actions_i, alpha_role)
```

This is explicitly an experimental candidate, **not an assertion** that
defensive opportunity can be observed or safely estimated from existing
datasets. Opponent-specific opportunity factors must be fitted on historical
observations strictly *before their own kickoffs*, then frozen by the
forecast decision deadline. Otherwise set the candidate's exposure to 1
and compare with the original role-based model. Missing individual actions,
workload or role labels must not be silently imputed to zero.

`scripts/experimental_individual_dc_propensity.py` implements a minimal
cutoff-aware, prior-shrunken DC propensity profile and neutral/workload
projection for research. Its source-observation contract is explicit;
there is no production integration.

## Acceptance experiment

1. Verify per-season availability of historical DC actions and timestamps,
   tactical role distributions, and a pre-match opponent-pressure proxy.
   Keep a coverage/missingness matrix by player and season.
2. Establish an immutable original-DC comparison arm with identical legal XI,
   minutes, event/scoring rules and seed handling. Do not include the
   experimental MM in this ablation.
3. Compare original DC, individual propensity without workload correction,
   and propensity with independently estimated opportunity correction.
   Predeclare developmental hyperparameter grids before later-period evaluation.
4. Score threshold Brier/log loss, NB count deviance, DC-point MAE, and full
   xP MAE/RMSE for both historic seasons. Report start/bench/role/low-history
   cohorts, block-bootstrap uncertainty and the percentage of matches with
   truly verified historical opportunities.
5. If opportunity data or provenance is insufficient, report **Not Available**;
   do not claim individual DC xP improvements or promote any candidate.

Production MM, PM, TS, chips, the original 2,125-point reference, and
`locked_model_active=false` must remain unchanged.

Unit tests authored in `tests/test_experimental_individual_dc_propensity.py`.
They are not asserted to have passed until a corresponding run is verified.
