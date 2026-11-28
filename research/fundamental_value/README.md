# Research C · Fundamental value and market inefficiency

Exploratory historical evidence from an independent replay and a price panel. See [results](REPORT.md), [data audit](DATA.md) and [logbook](LOG.md). All study code is isolated here.

## Model and mathematical alternatives

At origin (t), estimate minutes per match as ((M_i+90)/(n_i+2)) from lagged minutes and recent observation count. Use a shrunk attacking rate based on lagged xGI, a lagged non-attacking residual relative to appearance and attacking components, and a smoothed appearance-points proxy (min(2,mathrm{xM}/30)). This yields per-week (xP_i) under a constant match opportunity. Penalize volatile roles with (q_i=xP_i-0.25,mathrm{sd}(mathrm{minutes}_i)/90). A fixture sensitivity multiplies xP by mean projected match opportunity, based on the count of fixtures, home advantage and the opponent's lagged goal difference. Its final-calendar source makes that sensitivity retrospective.

1. **Surplus after budget opportunity cost.** In position (p), replacement (R_p) is the 75th percentile of (q) among players at or below the 30th price percentile. Define positional scarcity slope (lambda_p=max(0.1,(Q_{85,p}-R_p)/2)) in points per £m and excess price (P_i-F_p) with nominal positional floor (F_p). The score (G_i=q_i-R_p-lambda_p(P_i-F_p)) compares production in points at a common hurdle. A linear break-even price on this scale is (F_p+(q_i-R_p)/lambda_p). It can fall below the floor, indicating a negative surplus even at that floor. The slope is a heuristic, with a fixed £2m calibration span.
2. **Surplus per marginal budget.** (G_i^{ratio}=(q_i-R_p)/(0.5+max(0,P_i-F_p))). The £0.5m regularizer stabilizes players near the floor. This is a second market hypothesis and can favor bargains with comparatively small absolute upside.
3. **Squad marginal.** For valid squad (S), choose the XI maximizing (sum_{iin XI}q_i+max_{iin XI}q_i) over legal formations. Add 0.15 times the bench sum as a depth proxy in the transfer objective. A proposed swap or pair yields (Delta U=U(S')-U(S)). Its marginal depends on the existing XI, bench, captain and exact selling-value budget. Across planned holding period (h), the replay values it at (min(h,39-t)Delta U) less hits. This assumes persistent forecasts and reevaluates each week. The realized holding period can differ.

For a future full constrained valuation, let (W_h(B;i	ext{ in})) and (W_h(B;i	ext{ out})) be maximal expected net points with and without the player. Vary the purchase price in the first problem at fixed budget (B) and take the supremum price for which inclusion beats exclusion. The search must account for formation, club limits, captaincy, sub risk, bank, transfers and possible re-sale. Budget discreteness can create plateaus. The local swap marginal above approximates the immediate sporting part. No global shadow-price or re-sale optimizer was evaluated.

## Price test

Regress the change in recorded price from GW (t) to (t+3) on each standardized lagged signal individually. Include origin fixed effects, position, lagged price, goal difference, projected and observed minutes. Use the fixture-adjusted variant as a sensitivity. Positive ownership, returns from absence, newly observed starts, underlying attacking underperformance and haul signals are defined in code. A return from absence can represent benching or suspension. A new starter signal requires a change in recorded starts and cannot measure tactical-role change directly. The test estimates conditional association. It cannot identify the effect of ownership itself on mispricing.

Report £m per within-origin standard deviation. The larger of an eight-lag GW HAC and season-player clustered standard error is used as a dependence sensitivity. This is not joint two-way clustering. Holm correction covers eight signals within each sample and schedule specification. The two schedule specifications are correlated. See the separate tables before interpreting marginal intervals.

## Transfer replay

Three paired start squads per season, seeded at GW8 under a £100m budget. Same search, forecast, prices, starting squads and scoring for all arms. Baseline uses points and depth. Value adds 0.55 times the surplus score to the roster objective. Contrarian subtracts 0.5 times positional standardized log ownership. Momentum adds 0.5 times positional standardized net transfers. Combined uses 0.55 times surplus, −0.25 times ownership and +0.25 times momentum. Market ranks are capped at three SDs. The baseline is a proxy needed for internally consistent comparisons. The TS v3 arm requires genuine historical frozen inputs and was not evaluated.

Test 2, 4 and 6 GW intended holding periods. Search single moves among top 12 targets by position plus bounded two-move bundles. For each horizon require at least a 0.45-point projected gain after subtracting hits. Bank transfers with a cap of two through 2023–24 and five in 2024–25. Hits cost four points each above the free balance. Sell at current price on losses and round half of positive purchase gains down to £0.1m. Use lagged snapshot prices for all simulated transactions. There are no chips, forced moves on stale player records, explicit future transfer option value, or three-plus moves in a week. These restrictions apply to every arm. Score GW8–38 including captain/vice and formation-constrained bench substitutions using realized minutes. Compare paired outcomes and report six-GW circular block intervals for weekly differences averaged across starts. Seeds share the same season and are not independent replications. Replay intervals are descriptive and unadjusted across arms and horizons.

## Reproduce

From the repository root, install `research/fundamental_value/requirements.txt` in a virtual environment and run:

```sh
mkdir -p /tmp/fpl-c-data
source_pin=7ca01d3821a68ced454cd1f2195be40ed697629b
for season in 2022-23 2023-24 2024-25; do
  base="https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/$source_pin/data/$season"
  curl -fsSL "$base/gws/merged_gw.csv" -o "/tmp/fpl-c-data/$season.csv"
  curl -fsSL "$base/fixtures.csv" -o "/tmp/fpl-c-data/fixtures-$season.csv"
done
OPENBLAS_NUM_THREADS=1 python research/fundamental_value/run.py /tmp/fpl-c-data /tmp/fpl-c-results
python -m unittest discover -s research/fundamental_value -v
```
