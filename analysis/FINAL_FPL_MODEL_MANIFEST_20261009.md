# Final assembled FPL model — component manifest (2026-10-09)

## Canonical path
```
Historical deadline inputs
  → locked MM (minutes and playing probabilities)
  → locked PM/vFinal (fixture and player xP)
  → locked TS v3 (six-GW receding transfer/lineup planner)
  → frozen chip coordinator (FH / WC / BB / existing TC v2)
  → actual FPL scoring (captain, vice, autosubs, hits)
```

### Frozen parameters — do not retune during deployment
- MM: locked source `scripts/run_locked_mm_gw6_38.py`; historical replay GW6–38.
- PM/vFinal: locked generation `scripts/run_rolling_vfinal_gw6_38.py`.
- GW1–5: established cold-start; GW6–38: MM → PM/vFinal.
- TS v3: `(1.0, 0.60, 0.36, 0.216, 0.1296, 0.07776)`; horizon 6 GW; `rho = 0.60`; hit uncertainty buffer 1.0; official 4 points per paid transfer; 0–5 transfers, FT up to 5. Source `scripts/run_joint_fh_wc_stopping_replay.py` and `src/fpl_xpts/transfer_planner.py`.
- FH: λ=10.0, one-GW temporary team; restored team/FT/bank. Frozen module `src/fpl_xpts/simple_chip_thresholds.py`.
- WC: λ=20.0, permanent unlimited zero-hit transfers; six-GW TS action; same module.
- BB: λ=20.0, ordinary TS XI/bench, expected extra points = bench xP less expected autosub xP. `src/fpl_xpts/bench_boost_policy.py`. Values fit 2025/26 and checked conditionally GW6–38 in 2024/25.
- TC: pre-existing `TCV2Config` in `src/fpl_xpts/chip_planner.py`, `decide_tc_v2_from_samples` with current-GW option and structural unknown DGW value. No TC parameters retuned. `src/fpl_xpts/tc_chip_bridge.py` restricts current TC candidates to the manager's TS starting XI; TC's original potential future players remain available for option valuation. TC starts GW6 in historical replay because GW1–5 samples are absent.
- All four chips: at most one active chip per GW, each maximum once per 2025/26 half GW1–19 and GW20–38; chip use decision compares their **existing** adjusted exercise values. Pure arbitration module `src/fpl_xpts/final_chip_coordinator.py`. A selected TC captain may replace TS's captain but does not change selected XI or transfer path.

### Frozen checkpoints and test links
- Pre-BB FH/WC version: branch `chip-fh-wc-locked-20261009`.
- TS no-chips 2025/26 = 2,125 actual points (artifact source run 37612845586).
- FH/WC = 2,209 actual points (2025/26), conditional 2024/25 GW6–38 = 2,026.
- FH/WC/BB=20 = 2,242 actual points (2025/26), conditional 2024/25 GW6–38 = 2,060.
- Full integrated TC replay: `scripts/run_final_fpl_chain_replay.py` and `.github/workflows/final-four-chip-chain.yml`. Check the actual latest GitHub run/artifacts for certified integrated results. Do not claim 2,242+independent TC points without a common replay.
- Tests: `tests/test_final_fpl_chain.py`, `tests/test_bench_boost_policy.py`, `tests/test_simple_chip_thresholds.py`.

### Limitations: research / prospective deployment
- 2025/26 WC horizon sometimes built from conservative *as-of* future xP proxy rather than true PM target-GW forecast; cutoff-safe schedule needs production coverage.
- 2024/25 roster/price metadata timestamps are not independently certified.
- Archived TC candidate simulation uses historical final fixture calendars for future targets, **not fully cutoff-safe**. Its historical standalone TC gains do not prove that the candidate is owned by the assembled transfer strategy.
- A pure one-GW FH candidate can differ from actual FH value under stateful downstream transfer decisions. Historical point uplift is in-sample, not causal EV.
- Assembled model must pass end-to-end chip legality, FT/budget, points, and dependency provenance checks before deployment.
- This is the model logic checkpoint; integrating it into the publisher website is a separate UI/data wiring task.
