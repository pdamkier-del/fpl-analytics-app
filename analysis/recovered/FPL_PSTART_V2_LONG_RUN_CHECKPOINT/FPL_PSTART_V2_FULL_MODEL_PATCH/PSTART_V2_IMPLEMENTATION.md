# P(start) v2 — implementation checkpoint

## Status
Implemented as an append-only experimental layer. v1.0/v1.1 model files are not replaced.

### Core mathematics
- **Match Importance** has only three model blocks: dynamic competition value, round/stage, opponent strength.
- **Minutes** contains recent starts, recent minutes and short-term workload. No FPL chance-of-playing is used.
- **Position/Role** contains dynamic role share `q[i,r]` and slowly-changing first-choice hierarchy `H[i,r]`.
- Match Importance changes how strongly hierarchy matters; it is not simply added equally to every player.
- Final player-role assignment is entropy-regularised and constrained. Each player can occupy at most one starting slot and role capacities sum to 10 outfield + 1 goalkeeper, therefore `sum(P(start)) = 11`.

### Multi-competition data layer
New append-only tables:
- `club_matches_v2`
- `player_match_roles_v2`

Collector:
- `scripts/v1_1_backfill_fotmob_multicomp.py`
- discovers official matches by date and filters PL clubs
- keeps PL / UCL / UEL / UECL / FA Cup / League Cup
- caches every raw `matchDetails` JSON before normalization
- stores starters, minutes, matchday-squad membership and role/coordinates when available

FotMob is an unofficial/unversioned source. Raw caching and a tolerant parser are intentional so schema changes are auditable.

### Current holdout signal
Before this full data layer was populated, the available PL-only 2025/26 holdout gave:
- old P(start): Brier ~0.0877, log-loss ~0.3465
- v2-core: Brier ~0.0774, log-loss ~0.2595

This is encouraging but is **not** evidence for the full Match Importance/role system yet, because the checkpoint currently lacks historical cup/Europe lineups and granular roles.

## Reproducible order
1. `python scripts/v1_1_init_multicomp_pstart_v2.py`
2. Backfill 2023/24–2025/26 (development + holdout), then 2026/27 live-to-date using the FotMob collector.
3. Identity-map FotMob player/team IDs to stable project UUIDs.
4. Infer/update `q[i,r]` and `H[i,r]` deadline-safely.
5. Fit Match Importance coefficients and P(start) coefficients on development seasons only.
6. Freeze parameters.
7. Evaluate 2025/26: Brier, log-loss, reliability bins and `sum(P(start))=11`.
8. Only if P(start) improves, plug into xPts and run the expensive manager replay.

## Data-leakage rule
For a target PL fixture, only matches that kicked off before that FPL deadline may contribute to minutes, q, H, active-competition state, or Match Importance inputs.
