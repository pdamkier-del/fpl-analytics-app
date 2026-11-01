# Fixed offline simplification and market screen

This is research, not an app/model release. No production or B inference entry point imports either research script. All numerical decisions and candidate definitions were written in `protocol.json` before candidate scoring. No blend weights or named-player exceptions were selected after scoring.

## Reproduce

From the repository root, using the existing Core and archived research inputs:

```sh
PYTHONPATH=src:scripts:.:analysis /workspace/fpl-venv/bin/python scripts/locked_numerical_runtime.py analysis/screen_simple_market_model.py
PYTHONPATH=src:scripts:.:analysis /workspace/fpl-venv/bin/python scripts/locked_numerical_runtime.py analysis/summarize_simple_market_screen.py
```

The first command prepares the same 341 baseline tasks as the selected separated-goal-head replay. `--prepared-tasks path.json.gz` may reuse those exact prepared inputs. The locked numerical runtime matters: an initial unpinned preparation failed the reference marginal reproduction check and was discarded, rather than widening the tolerance. There is no new Monte Carlo sampling in the analytic candidate. Archived B xP has its original 400-draw sampling error.

## Arms

- `archived_B`: actual selected B historical replay, including existing MM, role-aware simulation and separated ordinary/penalty goals.
- `analytic_PM_frozen_MM`: exact same MM marginal distributions; additive analytic PM, preserving historical nonpenalty weights but replacing joint event allocation and bonus simulation.
- `analytic_PM_simple_MM`: same analytic PM, with a small recent-history MM ablation.
- `market_PM_frozen_MM`: same analytic PM and frozen MM, replacing only the two team goal means with odds-implied means.
- `market_PM_simple_MM`: both ablations with odds-implied team means.

The simple MM retains the frozen B starter prior with two pseudo-observations, availability locks and existing goalkeeper duration kernel. It is an **ablation, not a standalone simple model**. It constrains the expected starter count but does not verify role-compatible XIs, substitutions, or aligned TS scenarios. Missing appearances are not manufactured as bench observations.

The analytic PM computes appearance, goals, assists, clean sheets, defensive contributions, negative events, save buckets, penalty saves and a shrunk prior bonus rate. Ordinary goals and penalty attempts remain separate. It approximates recipient allocation with exposure-weighted shares; it does not claim equivalence to conditional on-pitch allocation. Its clean-sheet calculation uses the marginal duration and independent homogeneous Poisson conceded-goal process. It has no explicit time-varying score state, event correlation or jointly awarded bonus process. These are intentional simplifications under test, not claims that those mechanisms are unnecessary.

## Sources and timing

Football-data.co.uk supplies the two historical Premier League result/odds CSVs, attributed individually in `sources.json` with URL, actual retrieval time and SHA256. The mean non-closing 1X2 and over/under 2.5 odds are used, independently removing proportional bookmaker margin. Neither closing odds nor match outcomes are used to fit implied rates. Two Poisson means are fitted to the three independent market probabilities without outcome tuning; `fit_residual` records imperfect market/model agreement. Vaastav's season-specific FPL team lists supply explicit identity mapping; match joins require exact date and both club identities.

**An opening/non-closing label is not proof of availability before an FPL deadline.** These CSVs lack individual quote timestamps. The market arms therefore represent a timing-unverified diagnostic, potentially benefiting from later information. Regardless of score, they cannot be activated or described as deadline-safe superiority. An operational integration needs a licensed/authorized feed with archived capture times before each decision cutoff. Free historical coverage does not establish a production redistribution license or service guarantee.

Player history is restricted to prior matches at least four hours before each saved cutoff. Target labels are joined only after forecasts are produced. All periods have already been used in earlier research: none is an independent holdout. The scalar team comparison reports common Poisson log loss for the two means, not the current simulator's complete predictive likelihood.

## Evidence

`metrics.csv`: both seasons; all, played, rotation and keeper cohorts; minute MAE/bias, start and P0/P60/P90 Brier, point MAE/bias.

`team-metrics.csv`: team goal MAE/bias, Poisson log loss and clean-sheet Brier. `team-markets.csv`: all exact joined fixtures, fitted means and residuals. `decision.json`: reference marginal reproduction, input hashes, fixed screen checks and fixture-cluster bootstrap intervals. `predictions.csv.gz`: every scored player row for every arm. `rate-audit.csv.gz` is generated from existing nonpenalty input history and duplicates the established historical preparation, not a new fitted goal model.

No activation follows from a numerical screen pass alone. The minute-clock caveat and outstanding substitution-process issues documented in the 24 October audit remain unchanged. No physical simulation fix is claimed here.
