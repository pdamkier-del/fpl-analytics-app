# FH/WC simple threshold calibration — 2026-10-09

## Active research pipeline
- src/fpl_xpts/simple_chip_thresholds.py: two-parameter expiration-dependent choice.
- scripts/run_joint_fh_wc_stopping_replay.py: existing full-season replay; optional simple_thresholds mode evaluates *every* GW and corrects FH to a single-GW comparison. Existing stochastic mode remains available.
- scripts/run_simple_chip_replay.py: one full-season parameter pair.
- .github/workflows/simple-fh-wc-grid.yml: parallel 3x3 grid, parameters {0,10,20} xP, per-run outputs and logs.

FH marginal gain: optimal temporary Free Hit lineup expected score this GW minus expected score for locked TS normal lineup this GW after this week's normal transfer action.
WC marginal gain: current WC as TS-action six-week expected objective uplift relative to normal TS, using the existing as-of horizon proxy. No TC/MM/PM/TS code is modified.

Expiry caution = lambda * (end_gw - current_gw) / (end_gw - first_gw), separately for halves GW1–19 and GW20–38. Use a chip only if its surplus over its caution threshold is positive and greatest. One chip per GW.

## Legacy experimental pipelines (retained, not production)
- src/fpl_xpts/joint_chip_stopping.py: shock/Bellman approach, superseded as a decision *experiment* by simple threshold fit, not deleted.
- scripts/run_joint_fh_wc_calibrated.py and scripts/run_joint_fh_wc_stopping_replay.py default mode: previous empirical stochastic experiments.
- Other FH and WC audit/workflows remain necessary for reproducing historical results; do not delete until provenance audit.

## Calibration and interpretation
The 3x3 grid is exploratory. Rank by realised FPL points from the 2025/26 season, but call the maximum *in-sample*. Recheck on 2024/25 with genuine cutoff-safe data, and do not lock for live recommendations until multiweek forecast provenance is verified. The historical 2025/26 six-GW forecast relies on synthetic as-of proxy beyond its archived current GW, so expected margins are provisional.

Previously verified no-chip 2025/26 baseline: 2125. Prior stochastic WC/FH pilot: 2197 (+72), different model and not a benchmark for fit quality.
