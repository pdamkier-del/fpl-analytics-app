# TS v3 performance redesign

The original rolling planner was mechanically correct but too slow for a 38-GW
replay because it solved many medium-sized MILPs inside every beam node at every
hypothetical GW.

## Bottleneck removed
Old search:
- outer 6-GW beam
- multiple beam states per depth
- 1/FT/FT+1 transfer-count branches
- one lineup-aware MILP for every branch
- each MILP contained squad + XI + captain variables for all remaining GWs

That created thousands of MILP solves in a season replay.

## New fast candidate generation
The planner now defaults to `candidate_backend="fast_local"`.

For each hypothetical state it:
1. computes weighted player horizon values once;
2. keeps only the top few transfer targets per position;
3. enumerates legal one-transfer improvements;
4. builds multi-transfer bundles with a small local beam while preserving:
   - budget,
   - current sale value,
   - purchase price,
   - position,
   - max 3 per club;
5. hands only these plausible squads to the outer rolling beam;
6. scores those squads with the real lineup-aware manager objective
   (best XI + captain separately each GW).

So the heuristic is used only to PROPOSE candidate squads. The path objective
remains lineup-aware.

## Search pruning
At a hypothetical GW it searches all currently free transfers plus at most one
paid transfer. With 5 FT, all five can still be used. This removes unrealistic
deep hit branches while preserving the important FPL decisions.

Default fast settings:
- top transfer targets per position: 5
- local bundle beam: 10
- rolling beam: configurable
- 6GW horizon
- buffer 1.5
- chips off

The older MILP candidate backend remains available for targeted validation of a
deadline if needed.

## Verification
The existing TS v3 mechanics tests pass after the performance redesign,
including FT banking/cap, hit-buffer logic, weekly lineup flexibility and
execute-only-first-action behavior.

No new season replay has been started yet after this optimization.
