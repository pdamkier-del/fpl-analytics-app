# MM final architecture checkpoint — 2026-10-06

Scope: **Minute Model (MM) only**. PM and TS are not changed by this checkpoint.

## Decision

**MM architecture is now frozen as the agreed design.**

`MM_ARCHITECTURE_LOCKED = true`

`MM_PRODUCTION_PROMOTED = false`

The second flag is deliberately separate. The architecture and implementation
contract are complete, but GW22–38 has been reused during development and is not
a fresh independent holdout. We therefore do not relabel the model as
independently validated production truth.

## Locked MM decomposition

For every player-fixture:

[
E[M] = P(start) E[M|start] +
       (1-P(start)) P(sub|not\ start) E[M|sub].
]

The locked components are:

1. **P(start)**
   - role + hierarchy state
   - official-club-match workload
   - last-match performance residual
   - exact-11 team normalization

2. **P(sub appearance | not start)**
   - sequence-aware binary model
   - C = 4
   - 75% logit blend with the prior cameo estimate

3. **E[min | start]**
   - retained frozen starter-duration component

4. **E[min | sub appearance]**
   - 50/50 blend of frozen cameo duration and sequence-aware Ridge
   - Ridge alpha = 80

## Official match history

The workload state uses audited official club matches known before cutoff:

- Premier League
- Champions League
- Europa League
- Conference League
- EFL / Carabao Cup
- recovered FA Cup

Incomplete historical source coverage stays explicit. No missing role or player
identity is silently guessed.

### Role-history coverage

Verified role evidence currently available in the unified MM:

| Competition | Team-match sides | Role-player rows |
| --- | ---: | ---: |
| Premier League | 760 | 8,360 |
| Champions League | 43 | 473 |
| Europa League | 9 | 99 |
| EFL Cup | 25 | 275 |
| FA Cup | 14 | 154 |

Conference League remains usable in workload/minute history, but no source side
survived the strict verified 11-slot role-evidence gate. It therefore does not
update q/H rather than receiving invented roles.

For FA Cup, 56 PL-team sides and 970 player-minute rows were recovered. 14 team
sides currently satisfy the strict role-evidence gate; 42 are deliberately
excluded from q/H updates because starter identity/formation evidence is
incomplete. Their safe workload information can still be used where available.

## Locked role model

### q(i,r): role distribution

q answers: **which roles does the player actually play?**

It is based on recency-weighted role minutes. Match Importance has only a mild
effect on q because a low-importance match can still contain genuine evidence
that a player is used in a different role.

Selected development weight:

[
q_{MI\ scale}=0.10.
]

### H(i,r): role hierarchy

H answers: **how strongly is the player established in that role?**

Historical starts in more important matches carry more hierarchy evidence than
starts in low-importance matches.

Selected development weight:

[
H_{MI\ scale}=0.40.
]

The importance floor is 0.35, so a low-importance official match still carries
real evidence rather than being discarded.

Thus, all else equal, starting in a high-importance Champions League knockout
match shifts H more than starting an early low-importance domestic cup match.

## Match Importance

Match Importance is restricted to the agreed three inputs:

1. **dynamic Competition Value**
2. **Round / Stage**
3. **Opponent Strength**

Fatigue is **not** part of Match Importance. Fatigue/workload belongs in the
minutes/workload block.

MI is not added as one common boost to every player's current P(start). Its
primary use is to weight historical role/hierarchy evidence.

Dynamic competition value is allowed to rise when the club has fewer remaining
competition opportunities, based only on cutoff-safe state.

## Exact-XI and availability

- Expected starter mass is normalized to exactly 11 per team.
- A player's expected start mass cannot exceed one.
- Availability/injury acts as a current availability cap.
- Injury does not erase accumulated hierarchy H.

## Sequence-history decision

An additional experiment replaced the league-state sequence features with
sequence history from every audited official club competition.

This was **rejected**.

Development GW16–21 worsened:

- chosen unified league-sequence RMSE: **21.7486**
- all-official-sequence RMSE: **21.7673**

The all-official-sequence version produced only a tiny RMSE gain on the already
reused GW22–38 diagnostic (21.4659 old combined -> 21.4619) while worsening
development.

Therefore cup/Europe matches enter MM through workload and verified q/H, while
the start/substitution sequence remains Premier-League-state-specific because
it models the state transition in the competition being forecast.

## Uncertain-starter correction decision

A targeted residual correction for uncertain starters was also tested.

Best development candidate (`recent_start_minutes`, L2=40) substantially
improved the development uncertain-player slice, but on reused GW22–38 it
worsened the unified model overall:

- xMins MAE: 11.5499 -> 11.5843
- xMins RMSE: 21.4464 -> 21.4982
- state log-loss: 0.43554 -> 0.43698

It is therefore retained as a diagnostic idea, **not** part of locked MM.

## Current unified diagnostic

Against the previous combined MM on the same reused GW22–38 rows:

### Previous combined MM
- state log-loss: 0.437711
- state Brier: 0.232550
- xMins MAE: 11.444301
- xMins RMSE: 21.465868
- xMins bias: -0.222459

### Unified agreed-architecture MM
- state log-loss: **0.435540**
- state Brier: **0.231644**
- xMins MAE: 11.549921
- xMins RMSE: **21.446396**
- xMins bias: **-0.164589**

The unified MM therefore improves the mean-oriented RMSE objective, probability
state calibration, and mean bias, while MAE is worse by ~0.106 minute.

Expected minutes is a conditional-mean input to xP, so RMSE remains the primary
selection objective; MAE remains a guardrail and is reported rather than hidden.

## Known residual weakness

The hardest population remains uncertain starters.

On the reused diagnostic, players with P(start) roughly 0.2–0.8 have minute
error around 30 MAE / 34.5 RMSE. The targeted correction experiment did not
generalise well enough to justify another model layer.

This is recorded as model uncertainty rather than overfit away.

## What is now frozen

Do not change these silently during PM or TS work:

- four-part expected-minutes decomposition
- exact-11 allocation
- availability-as-cap logic
- official-club workload architecture
- q/H role architecture
- strict role-evidence gate for non-PL matches
- MI inputs limited to Competition Value + Stage + Opponent Strength
- MI applied primarily to historical H evidence
- q MI scale = 0.10
- H MI scale = 0.40
- MI evidence floor = 0.35
- current performance residual component
- league-state sequence subappearance component
- frozen starter duration
- 50/50 sub-duration blend, Ridge alpha 80

Any future MM change must be a separately named experiment and may not be
introduced indirectly while tuning PM or TS.

## Final status

The MM implementation now matches the agreed conceptual architecture closely
enough to freeze and move on to PM.

The remaining limitation is validation, not an undefined model design:
GW22–38 is reused diagnostic data, historical non-PL source coverage is not
perfect, and a genuinely fresh independent period is still required before
claiming production-level generalisation.
