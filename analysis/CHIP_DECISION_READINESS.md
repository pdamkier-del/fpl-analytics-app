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

## Joint FH/WC stopping prototype, 2026-10-09

- src/fpl_xpts/joint_chip_stopping.py: no-clairvoyance finite-horizon
  Bellman approximation with four chip-right states and three abstract
  squad-availability health states. FH is temporary, WC resets the health
  state. One chip per GW.
- scripts/run_joint_fh_wc_stopping_replay.py: 2025/26 held-out pilot using
  previous locked TS baseline and historically derived BGW/DGW frequencies.
  Pilot score 2115 versus locked 2125 (FH GW18,36; WC GW6,26).
- GW6 controlled stress: initial prototype still chooses WC in GW6 for
  healthy, three-starters-out-one-GW, and three-out-six-GWs. This IS a
  model defect/shortcoming; do not infer the strategy is correct.
- scripts/calibrate_joint_squad_shocks.py: 2022–2025 retrospective
  appearance-based proxy over 45 regular 10-fixture GWs; in 13,500
  bootstrap hypothetical XI draws 53.32% had 1–2 sudden nonappearances,
  5.30% had >=3, and next-GW zero persisted for 47.29% of flagged players.
  This is **not** injury-specific and samples are not independent.
- Historical 2024/25 WC-as-TS same-metric candidate objective gains:
  GW12 11.04 xP (6GW objective); GW20 18.50 xP. Only two points,
  so baseline future WC value is highly uncertain.
- The prototype's historical forward WC gain baseline was an arbitrary
  4.0 xP, materially below both matched historical observations, thus
  overly encouraging immediate WC. scripts/joint_chip_historical_priors.py
  loads calibration in consistent WC/TS horizon units and avoids mixing
  historical one-GW FH raw gaps as six-GW utility.
- scripts/run_joint_fh_wc_calibrated.py and
  scripts/run_joint_gw6_stress_calibrated.py are new held-out reruns.
- Evaluation caveats: only preselected candidate checkpoints, extra
  evaluation on severe availability drops; future squad is a three-state
  Markov abstraction, not a full stochastic TS roster replay. Even after
  calibrating, do NOT lock automatic FH/WC until all-week cutoff-safe
  forward forecasts, stronger sample and cross-season validation exist.

## Held-out 2025/26 calibrated joint-policy pilot (success)

- Run 37914368681: locked baseline 2125; stochastic joint FH/WC
  2208 actual points (+83), FH GW6+GW36 and WC GW19+GW34.
  TS/MM/PM locked unchanged. Chip decisions use forecast expectations;
  the +83 is realised single-season outcome, NOT estimated causal EV.
- Same held-out GW6 state: healthy FH gain 17.89, WC gain 23.93
  six-GW TS-objective points; q_save_both 37.30, q_FH 42.23,
  q_WC 37.51: FH exercised.
- Synthetic 3-starter disruption for only GW6:
  q_save 39.57, q_FH 50.85, q_WC 43.59: still FH.
- Synthetic 3-starter disruption for GW6-11:
  q_save 39.57, q_FH 47.42, q_WC 44.19: still FH.
- The WC early-use problem was mitigated, but FH still fires at GW6.
  This could be consistent with the forecasted FH gain but MUST be
  audited using independent forecasts and opportunity-value calibration.
- Research constraints: stochastic future health is a 3-state
  approximation; only a subset of deadlines has expensive WC/FH evaluations,
  future FH baseline is not yet calibrated in six-GW TS units,
  and persistent injuries are not modelled player by player. DO NOT deploy
  or lock chip decisions based on this one-season +83.

## Current provisional version: persistent-vs-temporary calibration revision

Git commit a556dfcd76b478573ea49e1c33af2b2f0c3f7454 changed the
three-state stochastic shock payoffs. This changed RESULTS; DO NOT confuse
them with the prior +83 variant.

- Independent replay runs 37914385670 and 37914460593 both returned
  locked baseline 2125 and calibrated joint-chip result **2197** (+72).
  FH GW6/GW36; WC GW8/GW34; 60 transfers and 16 hit points.
- In the GW6 actual as-of forecast, incremental FH six-GW utility=17.89,
  WC=23.93. Joint Bellman continuation q_normal=33.83,
  q_FH=38.31, q_WC=37.90, so FH leads WC by just 0.41 xP.
- In the controlled 3-starter outage stress, missing only GW6:
  FH action; missing GW6–11: WC action. This is the desired
  *directional* behavior but does not prove general optimality.
- The point gain is dominated by realised GW8 +50, GW34 +43,
  and GW6 +33 vs locked no-chip season (GW17 +29 without a chip
  arose indirectly from the changed permanent squad/transfer history).
  Point outcomes should not be interpreted as calibrated policy EV.
- The +83 run 37914368681 used the *earlier* shadow-state
  model, because another commit changed the branch between
  simulation launches. Different model versions explain the distinct
  scores; no identical-code replay discrepancy was demonstrated.
- Workflow .github/workflows/joint-fh-wc-calibrated.yml now checks out
  ${{ github.sha }} and sets fixed Python hash and BLAS thread
  environment for explicit commit provenance. Maintain this practice.

**NOT LOCKED**: future FH continuation baseline 4 xP and the
2-observation WC prior remain weak. Snapshot-level 6GW player forecasts
and conditional 15-player injury/discipline simulations are still
missing. The current policy evaluates a screened set of GWs, not
every possible deadline, and is not a production-optimal strategy.
