# TS v3 broad-search runtime checkpoint

Continued from branch HEAD `60b890a2feb84f68728495e7d2ebafeaf874cef0`,
not from the older `83245687` checkpoint. Runtime changes are published in
`eacb255aa1b9a3dcb826fc2d64cbf90b2cd362b2`.

## Runtime changes

The inner bundle loop now uses deadline metadata dictionaries instead of
repeated pandas row lookups. Weighted horizon values and target lists are
prepared once per path depth. Feasible bundles are reused across nodes with
the same squad, purchase prices and bank; FT remains in the path state and
changes penalties and future transitions. Sale prices are cached at the current
deadline. Weekly XI/captain scoring and the rolling path objective are unchanged.

Search settings are unchanged from the starting HEAD: 18 targets per position,
local bundle beam 60, 12 returned candidates per depth, outer beam 20,
0–5 transfers per hypothetical GW. There is no FT+1 cap in the fast-local backend.
The candidate proposer remains a heuristic based on weighted player values;
this is a broad beam search, not an exhaustive global optimum.

## Verification

- 16 planner/replay tests passed, including all transfer counts 0–5 with only 1 FT.
- GW1: all 61 proposed squads identical, in order, to starting HEAD.
- GW1: complete 6GW path and objective identical to starting HEAD.
- Candidate generation: 1.4293 seconds before, 0.0430 seconds after (33.3x).
- Full GW1 plan: 127.2598 seconds before, 3.3141 seconds after (38.4x).
- Resume test from GW23 preserved history and reproduced the same executed move
  and actual score (25 points) as the uninterrupted replay.
- Season checks: all 38 deadlines, 213 planned steps, first action only,
  nonnegative bank, FT cap 5 and exact 4-point hits / 1.5 paid-transfer buffer.
- No forced club-limit repairs occurred in this TS v3 replay.
- Point-model code and forecast inputs were not changed or refit.

The replay saves state, purchase prices, bank, FT, totals, logs and all planned
paths atomically after every GW. Resume rejects mismatched code/input fingerprints.
The Actions workflow is manual and preserves partial artifacts even on failure;
it no longer starts duplicate season runs on every code push or uses git push
for result publication. This run is published through the authenticated GitHub API.

## Result scope

2025/26 GW1–38, recovered rolling Phase5Q strategy proxy, chips OFF,
weights `(1.00, 0.85, 0.70, 0.55, 0.40, 0.25)`, paid-transfer uncertainty buffer 1.5.
Both strategies use the same initial squad, realized outcomes, lineup rules and
sale-value mechanics. TS v2 retains its existing static-horizon policy and 2.16
saved-FT charge; TS v3 uses endogenous FT state in the rolling path.
This is not evidence for final vFinal forecast performance or an independent holdout.

Full TS v3 runtime sums the 38 weekly planning/evaluation durations; input loading,
checkpoint writing, validation benchmarks and the TS v2 comparator are excluded.

## Completed 38-GW comparison

| Metric | TS v2 static 6GW | TS v3 rolling 6GW | v3 minus v2 |
|---|---:|---:|---:|
| Net actual points (after hits) | 2,137 | 1,992 | -145 |
| Transfers | 54 | 45 | -9 |
| Hit points deducted | 68 | 32 | -36 |
| No-transfer control | 1,425 | 1,425 | 0 |
| Uplift versus no-transfer control | +712 | +567 | -145 |
| Measured runtime, seconds | 353.22 | 174.65 | -178.57 |

The fresh TS v2 run reproduced its archived 38 gameweek logs exactly.
TS v3 scored 1,039 points in GW1–21 and 953 in GW22–38, versus TS v2's
1,160 and 977. Thus 121 of the 145-point gap occurred in GW1–21.

The runtime task is complete without narrowing the starting HEAD search.
TS v3 is faster but does not outperform TS v2 on this proxy. The local candidate
ranking still uses summed player horizon xP to propose squads, while final path
scoring uses actual weekly XI/captain utility. Candidate quality is a plausible
next investigation, not a demonstrated explanation of the entire score gap;
this checkpoint deliberately preserves the existing search behavior.

Results, complete planned paths, resumable state, source/output hashes and
verification evidence are in `analysis/results/transfer-strategy-v3-replay-20261005-v2/`.
