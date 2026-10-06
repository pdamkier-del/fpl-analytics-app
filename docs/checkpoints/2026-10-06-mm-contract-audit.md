# MM audit — agreed design vs current implementation

Date: 2026-10-06
Scope: Minute Model (MM) only. PM and TS are explicitly out of scope.

## Agreed MM contract

MM is the full player-minute process:
1. P(start)
2. P(sub appearance | not start)
3. E[min | start]
4. E[min | sub appearance]
5. xMins = P(start)*E[min|start] + (1-P(start))*P(sub|not start)*E[min|sub]

P(start) has three conceptual blocks:
- Match Importance
- Minutes / workload
- Position / Role

### Match Importance
Only:
- dynamic Competition Value
- Round / Stage
- Opponent Strength

It must NOT be a common additive player boost. It should chiefly modulate how
strongly role hierarchy H separates first-choice players from alternatives.

### Minutes / workload
Use all official club matches known before the forecast cutoff:
- Premier League
- Champions League
- Europa League
- Conference League
- FA Cup
- EFL / Carabao Cup

Signals include recent starts, recent minutes, short-term workload/fatigue and
rest. Recency / half-life must be fit without future leakage.

### Position / Role
- q(i,r): dynamic role distribution from recency-weighted role minutes.
- H(i,r): dynamic role-specific hierarchy.
- A player may occupy multiple roles.
- Role capacity is team/formation dependent.
- q/H must be pre-deadline and must not use the target lineup.
- Official non-PL club matches must be eligible to update the state when their
  role evidence is sufficiently identified.

### Allocation
- Team expected-start mass = exactly 11.
- Player start mass <= 1.
- Availability/injury is a current cap, not a destructive update to H.

## Audit result

Overall: **FAIL — MM is not yet the agreed final model and must not be locked.**

### PASS: minute decomposition
Current combined candidate explicitly models:
- P(start)
- P(sub appearance | not start)
- starter duration
- substitute duration

The xMins identity is implemented correctly.

### PASS: exact-XI normalization
The P(start) implementation retains the exact-11 team constraint.

### PASS: cutoff discipline in the tested foundation
Historical role/workload states use pre-cutoff evidence and the frozen diagnostic
reproductions have explicit leakage checks. The remaining historical
kickoff+3h availability rule is a reconstruction proxy, not observed ingestion
time, and must stay labelled as such.

### PASS: role-aware state exists
q/H, dynamic role capacities, multi-role q distributions and role competition
features exist and materially improve the old baseline.

### PARTIAL: official non-PL workload
The workload layer currently contains PL plus an audited subset of:
- Champions League
- Europa League
- Conference League
- EFL Cup

The new 2026-10-06 FA recovery adds:
- 43 FA Cup events seen
- 56 PL-team match sides
- 970 player-minute rows
- 970/970 recovered rows mapped to internal player UUID after FPL mapping

But only 14/56 team-match sides are currently flagged fully complete and 150
source lineup rows remain unresolved. Therefore FA workload is usable as an
audited partial source, but all-official-match coverage cannot yet be claimed.

### FAIL: role q/H is still PL-only
This is the largest structural mismatch.

The reproducible role audit explicitly records:
"scope": "2025/26 PL roles only".

Therefore Europe/FA/EFL matches may affect workload but do not consistently
update q/H. This violates the agreed architecture because a cup/Europe start,
role switch or rotation pattern should be able to update the player's role
distribution and hierarchy when role evidence is available.

### FAIL: Match Importance is not established as a stable final component
The new hierarchy-modulated implementation follows the requested structure:
- Competition Value
- Stage
- Opponent Strength
- interactions with H only, not a common additive player intercept

Development GW16-21 improved slightly:
- log-loss: 0.247174 -> 0.245643
- xMins RMSE: 21.7348 -> 21.6644

But reused GW22-38 became materially worse:
- log-loss: 0.243379 -> 0.253194
- xMins MAE: 11.5190 -> 12.5830
- xMins RMSE: 21.5579 -> 21.9192

Therefore the current MI parametrisation must NOT be promoted. The design is
correct; the current feature construction / active-competition timeline /
stage/opponent calibration is not sufficiently robust.

### PARTIAL: FA Cup is recovered but not integrated into the locked combined MM
The current combined candidate manifest still points to:
analysis/results/workload-recovered-v4/all_features.csv.gz
whose own coverage audit says FA Cup is absent.

The separate FA+MI experiment rebuilds those features with FA Cup, but the
combined MM itself has not yet been refit on that new source. So claiming the
current combined candidate already includes FA Cup would be false.

### PARTIAL: current combined candidate performance
The current combined exploratory MM improves the earlier v4 diagnostic:
- start log-loss: 0.244381 -> 0.243136
- state log-loss: 0.571050 -> 0.437711
- xMins MAE: 11.4738 -> 11.4443
- xMins RMSE: 21.5832 -> 21.4659

This is useful evidence, but it was sequentially tuned and GW22-38 is reused,
so it is not a clean independent promotion test.

## What is already acceptable to retain

Retain without redesign:
- exact-11 allocation
- P(start)/substate/duration decomposition
- sequence-aware sub appearance model
- performance residual signal
- role q/H concept
- availability as a cap rather than hierarchy deletion
- official non-PL workload architecture
- the Match Importance *conceptual* structure

## Required MM fixes before lock

1. Integrate recovered FA Cup into the canonical workload builder and regenerate
   the current MM feature table with explicit completeness flags.
2. Extend role-history ingestion beyond PL so official cup/Europe matches update
   q/H when reliable starter role evidence exists; unknown roles must remain
   unknown rather than being guessed.
3. Rebuild Match Importance from cutoff-safe active-competition state and
   calibrate Competition Value / Stage / Opponent Strength interactions without
   relying on the reused diagnostic for selection.
4. Refit the complete MM once on the unified official-match history.
5. Run diagnostics by:
   - Europe-active vs not
   - recent cup/Europe match vs not
   - role-change cases
   - uncertain P(start)
   - team
   - position
6. Only after the above, freeze one MM artifact and its model contract.

## Lock status

MM_LOCKED = false

Reason:
The current implementation is close in decomposition and workload mechanics,
but it is structurally incomplete relative to the agreed design because role
history remains PL-only, FA Cup is not in the canonical combined candidate, and
the first fully structured Match Importance implementation does not generalise
on the reused later-season diagnostic.
