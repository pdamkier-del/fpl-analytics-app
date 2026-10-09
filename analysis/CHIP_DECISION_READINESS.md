# FH/WC decision layer — evidence and acceptance gate (2026-10-09)

## Locked components
MM, PM/vFinal, TS v3 and its six-gameweek receding planner, weights
(1,.60,.36,.216,.1296,.07776), hit uncertainty buffer 1.0.
2025/26 no-chip reference = 2125 actual points. No changes to these modules.

## Confirmed defect in prior WC pilot
- The 2025/26 archived rolling vFinal has **only the current decision GW**
  at each origin GW6–38, despite the TS/WC six-GW horizon.
- The old WC optimizer therefore optimized for a single fixture week and
  discarded all 15 players at GW20; its predicted six-GW Q was not real.
- When comparing a WC roster to incumbent players, retained players must
  cost their SALE price (effective cost of retention), not market BUY price.
- A persistent WC squad needs viable reserves and may need a very different
  forward XI from the best current-week FH XI.

## Implemented experimental fixes
- src/fpl_xpts/wildcard_planner_v2.py: price-correct WC MILP; bench
  availability proxy; separate permanent state; and a conservative synthetic
  horizon built exclusively from information available at the deadline.
- tests/test_wildcard_v2.py: regression checks for incumbent sale value,
  no next-origin leakage, and unknown future fixture handling.
- scripts/run_wc_v2_audit.py: 2025/26 GW6 and GW20 forced-WC replay.
- scripts/run_wc_2024_conditional.py: cross-season diagnostic with archived
  true multiweek forecasts, metadata capture clocks unverified.
- These are **research pilots**; never treat the synthetic six-GW estimates
  as genuine fully cutoff-certified PM forecasts.

## Production readiness gates
1. A reproducible multi-GW as-of forecast, including game-specific projected
   player xP, player minutes and known fixture blanks/doubles, using only
   schedule snapshots available at each decision deadline. Unknown fixtures
   need scenario probabilities, not retrospective final calendar events.
2. Evaluate normal TS, WC and FH on *the same units and same stochastic
   scenarios*. WC alters purchase prices, owned team and all later states.
   FH restores the permanent squad, bank and stored FT.
3. Fit future injury, suspension and minutes-drop shocks from pre-deadline
   player histories; retain team/player correlated catastrophes and recovery
   duration. Model the impact on actual squad and normal transfers — not a
   separate arbitrary bonus for catastrophe, BGW or DGW.
4. Use an approximate Bellman optimal stopping algorithm, not hindsight
   maximum future FH gaps. Handle one chip per GW, one WC/FH per half
   and expiration at GW19/GW38 in the 2025/26 rules.
5. Validate locked baseline is unchanged, state/budget/team legality, chip
   FT accounting, forecast origin timing and leave-one-season-out performance.
   Compare expected uplift and realised points, and report forecast-error
   calibration instead of tuning rules to 2025/26 realised outcomes.

**AUTO-RECOMMENDATION DISABLED**: no FH/WC v2 pilot can be locked or deployed
until forecast provenance and cross-season performance pass the gates.

## Completed full-season diagnostics

- 2025/26 no chips 2125. Original one-week WC at GW20 1925.
- 2025/26 v2 as-of proxy: forced WC GW6 2032; forced WC GW20
  2050; 2025/26 still missing true as-of multi-GW forecasts.
- 2024/25 conditional GW6–38 baseline 1880 (not GW1–38).
  Using actual archived multi-GW projections: WC GW12 1976 (+96);
  WC GW20 1844 (-36). No selection policy was optimised; the dates
  were forced and cannot establish a general recommendation.
- 2024/25 historical price/team metadata clocks remain unverified.
- Independent WC unit regression workflow passed.

Links: 2025 pilot GitHub Actions 37907326651; 2024 conditional
GitHub Actions 37908351533; regression 37907826561.

The model is **not locked**. A positive predicted six-GW wildcard gain
can coexist with a realised loss, and both intra-season timing and
forecast uncertainty must be evaluated prospectively.

## WC as expanded TS action — verified replay (2026-10-09)

Experimental source: src/fpl_xpts/wildcard_ts_action.py. Reuses the locked
TS v3 deadline candidate MILP (unrestricted change count for the WC first
move) and the identical TS v3 continuation for later GWs, with official
zero WC transfer hits, permanent squad/bank/purchase-price updates and
retained FT. Candidate search is finite (top two MILP candidates plus
incumbent and normal first action); it is not a global solution of all
possible 15-man combinations.

2025/26 complete GW1–38 replay, GitHub Actions 37911278371:
- TS no chips: 2125 points (44 transfers, 28 hits).
- WC only GW6: 2088 (-37).
- WC only GW20: 2067 (-58).
- WC GW6 and GW20: 2121 (-4), 62 total transfers, 24 hit points.
- Greedy checkpoint selection (6,10,14,18,20,24,28,32,36), only if
  WC Q > normal Q: 2121, selects GW6/GW20. This is NOT a full optimal
  stopping policy and does NOT price the option of saving WC.
- WC GW6: Q lift +23.93 six-GW xP; actual GW6 64 vs 29 no-chip points.
  WC20 in dual run: Q lift +7.91; actual GW20 59 vs 88 no-chip points.

2024/25 conditional GW6–38 with archived multi-GW xP,
GitHub Actions 37911309255:
- TS no chips 1880.
- WC GW12 1992 (+112).
- WC GW20 1899 (+19).
- As-of metadata capture clocks are NOT independently verified.

Regressions tests/test_wildcard_ts_action.py: PASSED, run 37911301232.
Locked TS/MM/PM modules unchanged. Do not use these pilot outcomes as
evidence for statistically calibrated chip timing: 2025/26 future
horizon uses trailing as-of forecasts as proxies, and the optional value
of unplayed FH/WC plus future catastrophes remains unmodelled.
