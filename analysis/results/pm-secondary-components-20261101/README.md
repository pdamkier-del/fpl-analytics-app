# Secondary PM component calibration — 1 November 2026

This is a diagnostic replay of the audit branch, not independent historical
validation. The cohort has been used during prior research. Inherited parameter
fit clocks are not fully established; the 2024/25 nonpenalty goal coefficients
were fit on 2025/26 data. No component parameter is refit here.

The baseline is commit `20dfdd953ef99c382ea969836cd6a514b8182cc4`, with
341 frozen fixtures and predeadline inputs from the systematic precision audit.
Every fixture uses 2,000 draws. Fourteen fixtures, chosen without looking at
outcomes by evenly spaced (GW, UUID) indices within each season, additionally use
10,000 draws and a second independent seed. The 400/2,000/10,000 comparisons use
nested prefixes, not independent replications. Independent seeds measure MC
noise separately from fixture/player/GW sampling uncertainty.

## Labels and interpretation

* Saves, penalty saves, bonus, BPS, on-pitch conceded counts and negative events
  come from the frozen player-level labels. Save points and conceded deductions
  apply their deterministic FPL rules to these counts.
* **Direct independent player-CS labels: NOT AVAILABLE.** The player-CS tables
  are explicitly rule-derived from FPL minutes >=60 and the player's conceded
  count ==0. They never substitute a team's total goals conceded for a player's
  count. Team CS is evaluated separately. FWD has no FPL CS award.
* Actual substitution timestamps are NOT AVAILABLE in these labels. Boundary
  checks use deterministic synthetic own-goal events; they establish code
  semantics, not independent historical event-time agreement. Red-card exit
  and post-dismissal liability remain an inherited unsupported mechanism.
* 2025/26 DC uses the actual `defcon_points` award, including threshold-boundary
  checks against `defcon_count`. 2024/25 direct DC labels are NOT AVAILABLE; the
  model correctly disables that component in this season. Missing labels are
  never converted to zero or inferred from total points.
* BPS background means the residual after the same *partial* known-event function
  used by the simulator; unavailable Opta events remain background. 2024/25
  goal scoring has no penalty-origin ambiguity. 2025/26 scorers have only residual
  bounds because penalty-goal counts are NOT AVAILABLE. Exact residual grouping
  excludes those ambiguous rows. No 2026/27 outcome validation is claimed.
* Bonus probabilities are sampled jointly within each fixture. Rank/tie checks
  require a complete labelled actual-participant roster, including players with
  negative BPS. Every missing/incomplete case remains visible.
* The prediction population includes reserves and DNPs. Overall averages must be
  read alongside pregame xM/P(60+) bands. Actual-minute groups are diagnostics,
  not pregame cohorts. Club/player/source/prior groups overlap and are not
  independent candidate-selection tests.

## Reproduction

Python 3.12 and `requirements-model-checkpoint.txt`; use the locked launcher:

```bash
git worktree add --detach /tmp/pm-secondary-baseline 20dfdd953ef99c382ea969836cd6a514b8182cc4
cp analysis/results/pm-secondary-components-20261101/baseline-replay-source.txt /tmp/pm-secondary-baseline/analysis/secondary_components.py
(cd /tmp/pm-secondary-baseline && PYTHONPATH=src:scripts:.:analysis python scripts/locked_numerical_runtime.py analysis/secondary_components.py --out /tmp/secondary-replay --workers 4)
PYTHONPATH=src:scripts:.:analysis python scripts/locked_numerical_runtime.py analysis/secondary_component_report.py --predictions /tmp/secondary-replay/predictions.csv.gz --out work/secondary-report
```

The committed baseline predictions can regenerate the summary without simulation.
Use the baseline commit for baseline simulation; the PR supplies an explicitly
opt-in keeper-reserve adapter and preserves the sealed simulator and NP policy. The manifest records the
baseline source hashes; `baseline-replay-source.txt` preserves the exact executed
observer. The current observer additionally hardens source/runtime cache keys,
refuses source changes mid-run and excludes unlisted placeholders; its numerical
forecast law is unchanged. Use a fresh output directory for the archived observer. All forecasts are generated without passing outcome
labels into the timeline or event simulator.

`metrics.csv` contains MAE/bias/RMSE and binary Brier/log loss; `reliability.csv`
contains probability bins with counts. Separate 1,000-replicate deterministic
cluster bootstrap intervals use fixtures, players and GWs. They are dependence
sensitivity checks, not a combined two-way CI or multiplicity-adjusted evidence
for a parameter search. Sparse/rare events do not support recalibration.

The [validation report](../../audits/2026-11-01-pm-secondary-components-validation.md)
contains the acceptance decision and interpretation. `baseline-prefix-parity.json`
checks all 341 fixtures against the original 400-draw forecast rows.
`bonus-rank-ties.csv` records complete joint rank/tie checks;
`dc-threshold-boundaries.csv` records direct award/count consistency.
`mc-score-metrics.csv` compares losses on the fixed deep cohort; binary log loss
clips probabilities at 1e-6 because a finite sample can assign zero mass to a
rare event. Sparse flags/counts identify findings that cannot support tuning.

To reproduce the artificial sensitivity on the PR code:

```bash
PYTHONPATH=src:scripts:.:analysis python scripts/locked_numerical_runtime.py analysis/secondary_save_sensitivity.py --out work/save-sensitivity.json
```

Its audit wrapper compiles the original reserve expression and corrected
expression from the same B simulator, leaving application state untouched.
The synthetic penalty rate 1 is deliberately stronger than any frozen historical
input (maximum .20965); historical save-on-miss probability is .73333. The
synthetic results are a conditional conservation proof, not an expected historical
accuracy gain. GK save forecasts and scoring-rule parameters are unchanged.

The repair is available only through explicit research use:

```python
from fpl_v1_1_model.experimental_keeper_save_reserve import keeper_save_reserve
with keeper_save_reserve():
    # Call the existing B replay inside this context.
    ...
```

The adapter also exports `simulate_match(inp, rng, timeline=...)` for direct
paired experiments. No default, production, preview or approved policy is changed.
