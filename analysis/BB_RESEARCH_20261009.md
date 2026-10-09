# Bench Boost research — started 2026-10-09

## Locked dependencies
Frozen FH/WC release: branch `chip-fh-wc-locked-20261009`; FH holding parameter 10 xP, WC 20 xP. The MM, PM/vFinal, TS v3, and TC remain locked and untouched.

## BB baseline (experimental, not locked)
- BB is a **one-GW scoring overlay** on the permanent TS squad. No free transfers or temporary FH squad; normal transfer budget and hits are unchanged.
- Only one chip can be played per GW. There are two BB opportunities per season, one each half (GW1–19 and GW20–38).
- Naively summing four benched players' expected points overstates BB marginal value because the standard team already earns some bench points via automatic substitutions. Compute `BB_increment_xP = all_bench_xP - E[ordinary_autosub_bench_points]`.
- `src/fpl_xpts/bench_boost_policy.py` enumerates appearance patterns to estimate the autosub overlap, honouring legal formation and bench order. It assumes independent appearances solely for this correction; it does not change the locked minutes model.
- One BB caution parameter `lambda_BB * (period_end - gw)/(period_end - period_start)` follows the same diminishing opportunity-loss structure as FH/WC.
- `scripts/run_bb_locked_fh_wc_grid.py` replays the frozen 2025/26 FH/WC policy, samples BB opportunity in other GW, tests a grid of lambda_BB and evaluates realised extra bench points. It does not change underlying transfers, FH/WC timing, or TC.
- **Research caveat:** TC GW reservations must be injected using `--reserved-tc-gws` before claiming a fully legal all-chip simulation; absent that input, the grid is a diagnostic only. BB is not yet allowed to compete with FH/WC or trigger specific transfers to prepare the bench. Those features can be tested separately if justified by observed results.

## Quality gates
1. BB expected marginal points and official actual incremental scoring (accounting for autosubs) unit-tested.
2. Each half's selected BB must have no collision with previously locked chip actions.
3. Verify two-season out-of-sample point gains and cutoff integrity before locking the BB parameter.
4. No locked component edits or implicit recalibration.
