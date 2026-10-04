# Phase 5T — rolling Phase 5Q full-season replay

## Outcome

The rolling 2025/26 replay completed all 38 Gameweeks with the selected Phase
5Q core: legacy fixture-safe minutes, latent team goals with half-life 12 and
ridge 0.25, player attack allocation, defence/clean sheets, DefCon, saves,
negative events and joint Monte Carlo scoring.

| Policy | Net points | Gross points | Hits | Transfers | Points/GW |
|---|---:|---:|---:|---:|---:|
| Phase 5Q, standard six-GW transfer rule | **2,124** | 2,240 | 116 | 66 | 55.89 |
| Phase 5Q, no discretionary hits | 2,055 | 2,055 | 0 | 37 | 54.08 |
| Previous frozen-v1.0 engine control | 2,031 | 2,039 | 8 | 38 | 53.45 |

The standard Phase 5Q policy is +93 points (+4.58%) versus the v1.0 engine
control.  The no-discretionary-hit sensitivity is +24 points (+1.18%).  The
standard policy's extra 29 hit-bearing transfers therefore added 69 net points
relative to the conservative Phase 5Q policy in this one realized season, but
the turnover is too high to treat as a settled production transfer policy.

## Period split

| Period | Phase 5Q standard | Phase 5Q no-hit | v1.0 control | Standard minus v1.0 |
|---|---:|---:|---:|---:|
| GW1–5 cold start | 298 | 303 | 244 | +54 |
| GW6–21 development-assisted | 853 | 808 | 779 | +74 |
| GW22–38 later temporal validation | 973 | 944 | **1,008** | **-35** |

The aggregate win is therefore not clean evidence that Phase 5Q is better.
Its only later temporal-validation block, GW22–38, scored 35 fewer realized
points than the v1.0 control.  GW1–5 depends on a newly documented cold start,
and the DefCon parameters were developed on GW6–21.

## Rolling/cutoff implementation

For every decision GW, the state includes only matches with kick-off strictly
before the estimated FPL deadline (first kick-off in the GW minus 90 minutes).
That state is frozen and used to project the next six GWs.  Results from those
future matches are not used in that deadline's forecast.  The process then
repeats after completed matches enter the history.

The rolling implementation passed the Phase 5Q identity gate on GW22–38:

- all 8,023 Phase 5Q reference player-fixture rows matched;
- correlation in xPts was 0.99046;
- mean rolling-minus-reference xPts was -0.0040 per player-fixture;
- mean absolute difference was 0.1376, with independent 400-draw Monte Carlo
  noise contributing to row-level differences.

GW1–5 use previous-season player/team state as the cold-start layer.  From GW6
the selected current-season-only state is used.

## Prices

The replay uses the archived `value` for each player in each GW and applies the
official selling rule: price falls are taken in full; only half of a price rise
is retained, rounded down to the nearest £0.1m.

- 29,338 weekly player-price observations;
- 841 players;
- 100% non-null price coverage;
- 2,118 observed week-to-week price changes: 568 rises and 1,550 falls.

These are weekly deadline prices.  Complete daily 2025/26 bootstrap snapshots
are unavailable, so the replay does not choose an early transfer day within a
GW or model a price change that happens between the decision day and deadline.

## Rules and integrity

- 38/38 GWs and 15 players per managed squad;
- budget, bank, purchase prices and selling prices propagated through time;
- free transfers, hits, captain, vice-captain, autosubs, Bench Boost, Triple
  Captain, Free Hit and Wildcard applied;
- real-life club-transfer case producing four players from one club is resolved
  by a mandatory legalizing transfer;
- unit checks pass for selling value, captain/vice/autosub logic and the forced
  club-limit transfer;
- no negative bank and cumulative score reconciles to the GW log.

## Remaining limitations

1. Timestamped 2025/26 fixture-schedule snapshots are unavailable.  The replay
   uses the final archived GW assignment, so later blank/double rescheduling can
   leak into the six-GW schedule even though match-performance data do not.
2. Historical team-news and deadline availability snapshots are incomplete and
   are not reconstructed with hindsight.
3. DefCon was introduced in 2025/26; its selected parameters use GW6–21 for
   development.  GW22–38 is the relevant later validation block.
4. The aggressive transfer policy is a separate decision-layer weakness.  A
   single realized season cannot establish that 66 transfers/116 hit points is
   a robust strategy.
5. The previous 2,031-point run remains only the frozen-v1.0 engine control; it
   is not relabelled as a Phase 5Q result.

## Reproduction

```bash
PYTHONPATH=src python run_phase5t_rolling_reference.py
PYTHONPATH=src FPL_REPLAY_FORECAST=phase5q python run_phase5s_season_replay.py
PYTHONPATH=src FPL_REPLAY_FORECAST=phase5q \
  FPL_TRANSFER_POLICY=no_discretionary_hits python run_phase5s_season_replay.py
```
