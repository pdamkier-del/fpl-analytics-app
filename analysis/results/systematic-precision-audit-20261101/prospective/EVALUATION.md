# Frozen evaluation rule (2026-11-01, before GW10 deadline)

For each origin, the **first successfully captured sealed forecast** is the primary
prospective forecast. Later captures are retained, never substituted after outcomes.
For this origin use seal `fac23927e30490fba461894f61c00599f8c6697d38213c3bc40bea121bbfbafb`.
Origin GW10 is primary; GW11–15 are separate forecast-horizon diagnostics from the
same origin, never relabelled as new independent forecasts or pooled without origin
clustering. New GW origins get their own first-capture primary forecast.

Evaluate all archived forecast players, including zero-minute outcomes; do not
remove errors based on later injuries or lineups. Preserve missing labels as missing
and report coverage. Use finalized official FPL points/minutes/goals/FPL assists;
freeze labels with provider, acquisition time and hashes. Report minute MAE/bias,
start/60+/90 Brier, xP MAE/RMSE/bias, position and pregame-start-probability groups.
Report gameweek/fixture counts and fixture-cluster intervals. Freeze the Monte
Carlo draws already published; never regenerate a better-looking predeadline
prediction after the deadline. Sample intervals and MC estimation noise are separate.
No accuracy claim before outcomes; no fitting on this log before its declared test
period is evaluated. GW10–15 is the initial locked evaluation window.

The local hash chain detects accidental edits. Public git commit timestamps and the
CI artifact establish externally recorded timing; a local timestamp alone does not.
This ledger does not alter or publish any app/model forecast.
