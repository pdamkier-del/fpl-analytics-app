# Latest checkpoint: completed role-event simulation

See `2026-10-05-role-event-integration.md`. Role event layer implemented and
tested, not promoted. 1,200-draw nonbonus MAE: current v4 0.828379 vs roles
0.829757. 144 fixtures / 11,794 rows; reused GW22–38, not full season/holdout.
218 integrity checks pass. Website explicitly deferred; no website changes.
Current v4 retained. Full-season data and season-rule gates remain below.

## Previous checkpoint: minute component experiment and Saturday target

See `2026-10-05-minutes-components-and-release-plan.md`. The user has
authorized preparing the complete model, with minutes first and detailed
roles considered for other components, targeting Saturday 10 October.

Completed: exact signed minute-error decomposition; 27 frozen component
combinations selected using development GW16–21 RMSE; selected substitute-
duration hybrid tested through the original joint simulator on all 144 paired
fixtures. Original control predictions are exactly unchanged. 43 experiment
checks pass. No estimator refits or model/policy promotion.

The hybrid slightly improves minute RMSE but worsens minute MAE. Its paired
nonbonus point MAE is 0.834813 versus current v4 0.831744; point RMSE is
1.591309 versus 1.585767. With 80 draws these small stochastic differences
are not proof of inferiority; there is no demonstrated downstream gain.
Retain current v4 as reference.

Detailed role known for 3,121/3,168 actual starters in the paired cohort.
Roles already inform minutes. Event rates currently use broad-position
priors plus individual history. Next role experiment should add audited,
predeadline role information with shrinkage/fallback to xG/xA and DefCon
components, selected on development data before joint evaluation.

Full v4 season validation still has concrete gaps: 196 origin-target cells,
32 roster rows across 26 fixtures, early as-of states, competition coverage,
and separately controlled season-rule integration. The release plan records
these acceptance gates. GW22–38 remains reused diagnostic.

## Previous completed direct evaluation

See `2026-10-04-direct-minutes-v4.md`.

Exact shared point-diagnostic cohort: 144 fixtures / 11,794 player-fixture
rows, GW22–38, 26 whole fixtures excluded in both arms. Saved forecasts only;
no fitting, prediction regeneration, model or transfer/chip policy changes.

Original v2 → selected v4 workload_start:
- Minute MAE: 11.969695 → 11.509261 (3.85% reduction).
- Minute RMSE: 21.920483 → 21.573631.
- Start Brier: 0.077751 → 0.075779.
- Start log loss: 0.259617 → 0.246429.
- Ten-bin calibration ECE: 0.024988 → 0.007284.

Internal role-control is a separate comparator (minute MAE 11.847375),
not the unchanged v2 joint-simulator control. Direct minute metrics already
existed on the broader saved dataset; this report verifies the exact matched
cohort and corrects the prior overly strong conversational status claim.

Weaknesses: actual substitute minute MAE worsens 19.412683 → 20.640091;
forward start Brier worsens; larger role-information-change bands show small
MAE regressions. Much of the aggregate improvement comes from nonappearance.
All slices based on actual outcomes are posthoc descriptive, never features.

107 report integrity/metric/calibration/partition/policy checks pass;
target starts and minutes additionally match Historical Core exactly.
Existing full test suite: 125 passed. Full evaluated rows are checksum packed
in `analysis/results/direct-minutes-v4-diagnostic-v1/`.

GW22–38 remains reused diagnostic, not new holdout. No full v4 season-points
claim. Independent evaluation and incomplete competition histories remain.
The separately completed old-model season reproduction has 2,096 net points
but is irrelevant to the new minute-model comparison; its results remain intact.

The requested direct evaluation is complete. Do not change the model or policy
silently: new tuning requires a separately defined development experiment and
independent evaluation period.
