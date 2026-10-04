# Latest checkpoint: direct v4 minute/start evaluation complete

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
