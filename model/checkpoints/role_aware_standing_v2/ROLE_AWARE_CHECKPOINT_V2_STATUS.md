# FPL role-aware standing model — checkpoint v2

Date: 2026-10-01

## Frozen/kept decisions

- Keep P(start) v2 core. 2025/26 holdout Brier ~0.07743 vs old ~0.0878; full replay 2113 -> 2138.
- Fine-role model uses stable `player_uuid` as `external_player_id` wherever possible.
- Team IDs in v2 are season-safe: `<season>:<team_id>` (e.g. `2025-26:8`).
- Availability is a deadline cap, not hierarchy evidence.
- Matchday-squad absence does not count as negative tactical hierarchy evidence.
- Registration and transfer states are cutoff-safe; same-timestamp transfer writes `left` on old club and `registered` on new club.

## Registration / availability state now built

True timestamped FPL cutoff state already present in normalized DB:
- 2023/24: 29,510 player registration/status snapshots across 38 deadlines.
- 2026/27: 662 current snapshots.

Historical registration-only proxies reconstructed from full FPL roster rows (not injury status):
- 2022/23: 807 registered + 29 left.
- 2024/25: 815 registered + 31 left.
- 2025/26: 870 registered + 29 left.

Blank-GW bug fixed: a team roster is only updated in a GW if that team actually has a fixture; blank teams are not marked as departures.

Availability for 2024/25 and 2025/26 remains unknown/neutral when no true deadline snapshot exists. No post-match information is used to guess injury/suspension state.

## Availability rule corrected from historical calibration

`status=available` is authoritative and gives availability cap 1.0 even if a stale `chance_of_playing` value says 0/25/50/etc.

2023/24 evidence:
- available: n=18,636, start 42.40%, play 56.86%.
- available + chance=0: n=280, start 45.36%, play 73.21% -> chance field is clearly stale in these rows.
- doubtful: n=1,298, start 18.72%, play 33.59%.
- injured: n=2,889, start 0.42%, play 1.21%.
- suspended: n=194, start/play 0.52%.
- unavailable: n=6,447, start 0.03%, play 0.06%.

Current mapping:
- injured/suspended/unavailable/ineligible/out -> cap 0.
- available/a/fit -> cap 1, ignore stale chance.
- unresolved/doubtful + explicit chance -> use explicit chance as provisional cap.
- otherwise -> neutral cap 1.

Do not overfit the doubtful mapping yet; raw chance is predictive but not perfectly calibrated.

## Integrity audit

Current v2 DB audit:
- player_registration_v2 rows: 32,779.
- player_availability_v2 rows: 30,172.
- players active on >1 team at the same cutoff: 0.
- true cutoff availability rows without exact registered team row: 0.
- unknown stable player UUIDs: 0.
- malformed season-safe team IDs: 0.

## Detailed role data source found and importer implemented

Public source: `olbauday/FPL-Core-Insights`, 2025/26 Premier League detailed layer.
Validated source coverage:
- 380/380 PL matches.
- 15,153 lineup rows, including exactly 8,360 starters (=22 per match).
- 11,448 average-position rows.
- lineups contain match, team side/code, FPL player ID, coarse position, starting flag, formation.
- average positions contain x/y coordinates.

Adapter implemented: `scripts/v1_1_ingest_fpl_core_detailed_roles.py`.
It maps source FPL IDs -> stable player_uuid, maps source teams/fixtures to internal IDs, writes `club_matches_v2` and `player_match_roles_v2`, infers starter roles from formation + average-position geometry, and gives played substitutes the nearest role anchor. Unused bench players are retained with role NULL rather than inventing a role.

Role geometry convention observed in source: x increases toward opponent goal; low y is right side, high y is left side.

Formation-role unit tests currently cover 4-2-3-1, 4-3-3, 3-4-2-1 and 3-5-2.

## Current blocker

The complete 38-GW detailed CSV set is visible through the GitHub connector but is not yet materialized in the local Python/container runtime. The local runtime cannot currently clone/download the public repo directly. Therefore **no claim is made that the full 2025/26 fine-role backfill or fine-role replay has been run yet**.

Do not replace this with a coarse DEF/MID/FWD replay and call it validation of fine roles. The model plumbing is ready; the remaining data step is to materialize `GW*/fixtures.csv`, `GW*/lineups.csv`, and `GW*/average_positions.csv` locally and run the existing importer.

## Reproducible source downloader

`v1_1_download_fpl_core_role_data.py` now defines the exact 114 public source files required (38 GWs x fixtures/lineups/average positions), retries downloads, and refuses the full 2025/26 source if the published 380-fixture / 8,360-starter invariants fail. Its dry-run passes locally; network access, not URL construction, is the remaining runtime blocker.

## Tests

`PYTHONPATH=src pytest -q tests/test_pstart_v2.py` -> 11 passed.

## Next run order once detailed files are local

1. Run `v1_1_ingest_fpl_core_detailed_roles.py` for 2025/26.
2. Audit inferred roles by formation/team and inspect ambiguous formations.
3. Build cutoff-safe `q(i,r)` + `H(i,r)` with `v1_1_build_role_hierarchy.py`.
4. Blend new-signing cold-start role prior.
5. Apply deadline registration/availability.
6. Solve constrained P(start, role), generate role-aware xMins.
7. Compare against P(start) v2 core on 2025/26 without changing goal/assist models first.
8. Only keep role additions that improve calibration/forecast/replay without leakage.
