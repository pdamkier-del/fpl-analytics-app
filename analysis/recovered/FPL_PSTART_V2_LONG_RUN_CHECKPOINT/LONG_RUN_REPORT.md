# FPL P(start) v2 — long-run checkpoint

## Status

This run tests the new P(start) core without changing the rest of the event model. The full proposed non-PL layer (Champions League / Europa League / Conference League / FA Cup / League Cup lineups, Match Importance and role-level q/H states) is **not yet historically backfilled** because the accessible runtime could not retrieve a complete reproducible historical lineup source. The collector/schema/full-model patch is retained separately; no data were fabricated.

## 1. P(start) holdout — 2025/26 GW6+

Development seasons: 2023/24 + 2024/25 only. Holdout: 2025/26. No FPL availability.

- Old reconstructed P(start) Brier: 0.08792
- P(start) v2 Brier: 0.07743
- Old reconstructed log-loss: 0.34699
- P(start) v2 log-loss: 0.25953
- Relative Brier reduction: 11.9%
- Exact team constraint max numerical error: 5.33e-15
- Mean P(start): 0.27753; actual start rate: 0.27753

Core features: recent starts (half-life 3), slow hierarchy proxy (half-life 10), recent minutes (half-life 3), previous-GW start/minutes, FPL position, and exact sum P(start)=11.

## 2. Exact joint xPts sensitivity — GW22–38

Everything except P(start)/xMins is held fixed in the Phase 5E joint simulator. Matched player-GW sample n=6669.

### Bonus-neutral primary metric

| Metric | Old P(start) | v2 P(start) | Change |
|---|---:|---:|---:|
| MAE | 1.6547 | 1.6040 | -0.0507 |
| RMSE | 2.2702 | 2.2431 | -0.0271 |
| Bias | +0.1325 | +0.0865 | -0.0460 |

For comparison, the unchanged v1.0 simple non-bonus baseline has MAE 1.6277 and RMSE 2.3413. The paired GW-block bootstrap for v2 minus v1.0 gives MAE CI95 [-0.0553548216237777, 0.00391977924722101] and RMSE CI95 [-0.14254669324486638, -0.06126111966301491].

## 3. Full 2025/26 manager replay — apples-to-apples

Both runs use exactly the same replay code and policy: Phase 5Q rolling forecasts, simple 3-GW transfer search, 2-point hit uncertainty buffer, joint WC/FH/BB selection, TC disabled. GW1–5 are identical.

| | Old | v2 | Delta |
|---|---:|---:|---:|
| Total points | 2113 | 2138 | +25 |
| Transfers | 58 | 57 | -1 |
| Hit points | 84 | 84 | +0 |
| GW1–5 | 231 | 231 | +0 |
| GW6–21 | 924 | 912 | -12 |
| GW22–38 | 958 | 995 | +37 |

Old chips: {'wildcard': [6, 26], 'free_hit': [18, 36], 'bench_boost': [7, 28], 'triple_captain': []}

v2 chips: {'wildcard': [6, 28], 'free_hit': [17, 36], 'bench_boost': [12, 33], 'triple_captain': []}

The especially useful result is the later temporal period: **958 → 995 (+37)**, while GW6–21 falls by -12. This is more encouraging than a gain confined to the earlier development-assisted period.

## 4. Important limitation of the full-season replay

The exact Phase 5E joint simulator was rerun with v2 P(start) on GW22–38. The historical rolling Phase 5Q generator itself is absent from the available checkpoint, so the 38-GW manager replay cannot be regenerated exactly fixture-by-fixture with the new joint simulator. Instead the frozen rolling Phase 5Q xPts are adjusted using the cutoff-safe change in expected minutes. The translation strength (lambda=0.70, per-90 rate capped at 12) was calibrated only against **old-vs-new simulator outputs**, never against actual FPL points. Therefore the 2,138 result is a strong integration diagnostic, not yet the final score for the future fully regenerated model.

Rolling rows: 163459; adjusted rows: 140172; mean absolute xPts change per adjusted row: 0.1350; mean change: -0.0347.

## 5. Non-PL / Match Importance status

The full architecture is prepared for:

- all official club fixtures;
- dynamic Competition Value + Round + Opponent Strength Match Importance;
- dynamic role shares q(i,r);
- dynamic hierarchy H(i,r);
- role-aware player assignment;
- exact sum P(start)=11.

However, no complete historical cup/Europe lineup/minutes backfill was obtained in this runtime. Direct public API access was blocked and public GitHub searches surfaced collectors but not a complete committed 2025/26 raw lineup archive. That part must remain a data-acquisition task rather than being imputed or guessed.

## Decision from this checkpoint

The core P(start) change passes all three useful gates available now: probability calibration improves, exact joint xPts improves on the later holdout, and the apples-to-apples manager replay improves by 25 points overall / 37 points in GW22–38. It is therefore worth keeping as the v2 candidate while the non-PL Match Importance/role data layer is completed.
