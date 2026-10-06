# MM final lock — 2026-10-06

Status: **LOCKED for the current project iteration**

Scope: Minute Model (MM) only. PM and TS are unchanged.

## Final selected MM

The locked MM uses the best verified feature/state pipeline:

- role state q/H: preserve the existing audited pre-deadline PL role state
- workload: official club workload including PL, Champions League, Europa League,
  Conference League, EFL/Carabao Cup and the recovered FA Cup data
- P(start): role + workload logistic baseline with exact-11 normalization,
  followed by the retained last-match performance residual correction
- P(sub appearance | not start): retained sequence-aware binary model,
  C=4, blended 75% on the logit scale with the frozen baseline
- E[min | start]: retained frozen v4 starter-duration model
- E[min | sub]: 50/50 blend between frozen cameo duration and sequence-aware
  Ridge(alpha=80)
- exact expected starter mass = 11 per team/fixture

The xMins identity remains:

xMins = P(start) * E[min | start]
      + (1-P(start)) * P(sub | not start) * E[min | sub]

## Match Importance decision

The agreed Match Importance architecture has been implemented and audited:
- dynamic Competition Value
- Round / Stage
- Opponent Strength
- no common additive boost to every player
- historical high-importance games can weight role/hierarchy evidence, with H
  intended to receive stronger weighting than q

However, Match-Importance-weighted official-match q/H is **not enabled in the
locked MM**.

Reason: before judging non-PL role evidence, the new role-history replay was
tested on PL-only. It did not reproduce the stronger existing audited PL role
state and worsened both development and reused-diagnostic minute metrics.
Therefore it would be unsafe to replace the verified q/H state merely to satisfy
the desired architecture.

The MI-weighted q/H implementation remains in the codebase behind this evidence
gate. It should only be reconsidered after:
1. the PL role replay reproduces the audited role state sufficiently closely;
2. cup/Europe role identities/slots are more completely verified; and
3. evaluation uses genuinely fresh data rather than the already-reused
   2025/26 diagnostic period.

Official cup/Europe matches still contribute to workload/fatigue/rest in the
locked MM.

## Final performance

Development GW16-21:
- state log-loss: 0.453543
- xMins MAE: 11.3951 min
- xMins RMSE: 21.6707 min
- xMins bias: -0.0261 min

Reused diagnostic GW22-38, 13,987 player-fixture rows:
- state Brier: 0.231781
- state log-loss: 0.435694
- sub-appearance Brier among actual nonstarters: 0.078828
- xMins MAE: 11.4875 min
- xMins RMSE: 21.4376 min
- xMins bias: -0.2161 min

These GW22-38 numbers are diagnostic, not an independent holdout.

## Official-role ablation

The source audited PL q/H state with rebuilt official workload was the best
verified arm.

Rebuilt PL-only q/H already worsened development MAE by +0.092 min and reused
diagnostic MAE by +0.184 min.

Adding verified Europe roles to the rebuilt role state improved that rebuilt
state relative to rebuilt PL-only, but still remained worse than the existing
audited q/H state:
- development MAE +0.145 min vs final base
- reused diagnostic MAE +0.127 min vs final base

All-official q/H with Match Importance was also worse than the final base:
- development MAE +0.139 min
- development RMSE +0.067 min
- reused diagnostic MAE +0.106 min
- reused diagnostic RMSE +0.047 min

Therefore no official-role/MI rebuild is promoted.

## Uncertain starters

Definition used for the targeted audit:
0.20 <= P(start) <= 0.80

Development GW16-21:
- n = 833
- xMins MAE = 30.5034 min
- xMins RMSE = 34.7256 min
- state log-loss = 0.9469

Reused GW22-38 diagnostic:
- n = 2,644
- xMins MAE = 29.9128 min
- xMins RMSE = 34.6837 min
- state log-loss = 0.9709
- bias = -1.4655 min

A direct recent-start/recent-minutes correction to P(start) was tested. No
candidate passed the development guardrails. The final choice is therefore
**no additional uncertain-starter correction**.

This is important: we are not keeping a weaker correction merely because it
looks plausible.

## Where MM falls off

Worst uncertain-starter GWs in the reused diagnostic:

1. GW30 — MAE 33.72, RMSE 38.42
2. GW22 — MAE 31.93, RMSE 36.74
3. GW31 — MAE 31.78, RMSE 36.54
4. GW36 — MAE 31.44, RMSE 36.30
5. GW32 — MAE 31.28, RMSE 36.01
6. GW38 — MAE 30.28, RMSE 35.35
7. GW37 — MAE 30.27, RMSE 34.88
8. GW29 — MAE 30.23, RMSE 34.94

The largest errors are dominated by lineup shocks rather than a smooth
miscalibration:
- a player with little/no recent playing time suddenly starts and plays most of
  the match;
- a high-probability regular starter unexpectedly gets 0 minutes;
- goalkeeper/defender rotation shocks;
- late-season rotation and abrupt return/availability changes.

Examples in the diagnostic include severe misses for players such as Matty Cash,
Ben White, Daniel Muñoz, Martin Ødegaard and several goalkeeper/defender
rotation cases. These examples are descriptive, not new training labels.

## Known remaining limitation

The main unresolved MM error is **latent lineup information near the deadline**.
Simple recency/sequence features did not solve it robustly.

A meaningful future MM upgrade should therefore come from materially new
information, such as better deadline-time injury/availability/team-news and
manager-selection signals, rather than more tuning of the same historical
sequence features.

## Lock rule

MM is now locked for downstream PM/TS work.

Do not tune MM again against GW22-38.

Reopen MM only for:
- a genuinely independent season/time period;
- materially improved role/lineup ingestion;
- new deadline-available injury/team-news data;
- a proven exact reproduction of the audited PL q/H state before adding
  non-PL role-history weighting.

MM_LOCKED = true
