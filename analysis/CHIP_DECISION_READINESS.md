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
