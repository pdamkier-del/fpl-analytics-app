# MM v2 external rating + global XI contract

This contract defines the input Work should produce from FotMob/SofaScore and
how MM v2 consumes it.

## Rating ledger

One row per provider/player/match.

Required columns:
- provider
- player_uuid
- match_id
- available_at
- rating

Optional but strongly preferred:
- role
- minutes
- competition

Rules:
- rating on provider 0-10 scale
- no target-match rating may be available before its forecast cutoff
- duplicate provider/player/match rows are invalid
- provider rows are first collapsed to one player-match rating
- ratings are recency weighted
- ratings are normalized relative to role where enough history exists
- missing rating history is neutral, never punitive

## XI assignment

For each team/fixture:
1. generate allowed roles from q_i,r
2. combine q, H, base P(start), workload/availability and rating-derived
   performance score into player-role scores
3. evaluate legal formations
4. solve a maximum-weight bipartite assignment
5. exactly one player per slot
6. a player can occupy at most one slot
7. exactly 11 distinct starters
8. multi-role players may compete for multiple slots, but can win only one
9. retain probabilistic P(start) separately for xMins

The assignment is the coherent MAP-style XI used for explanations and
competition features. It must not collapse probabilistic P(start) to 0/1.

## Evaluation

Compare MM v2 against the locked MM base.

Primary:
- start log-loss
- start Brier
- xMins MAE
- xMins RMSE

Important slices:
- 0.20 <= P(start) <= 0.80
- lineup-shock GWs 30, 22, 31, 36, 32, 38, 37, 29
- multi-role players
- players with close same-role competitors
- recent rating uptrend/downtrend
- Europe/cup workload in previous 7 days

No promotion from reused GW22-38 diagnostic alone.
