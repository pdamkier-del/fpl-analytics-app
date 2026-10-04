# Latest checkpoint: legacy season simulation completed

See `2026-10-04-legacy-season-completed.md` for execution and limitations.

All 38 GWs executed: **2,096 net points**, 2,152 gross, 56 hit points,
50 transfers, 1,367 no-transfer control, £1.5m final bank. All 570 lineup
rows and 38 gameweek rows match the archive after autosub ID normalization.
Scores and autosubs were recomputed for every GW. Existing suite: 125 passed.

Small checkpoints published at GW5, GW19, GW30; final run_status has
completed=true and last_completed_gw=38. Protected policy hashes unchanged.
Exact historical bytes are recoverable from committed gzip parts.
Launcher resumes by default and reconstructs its scratch runtime.

This is a legacy technical reproduction, not v4 season performance and not
new holdout evidence. GW22–38 remains reused diagnostic. The original
runner's retrospective metadata/schedule and inherited rule limitations
are retained and documented; transfer/chip policy was not changed.

No further execution is needed for this legacy simulation. A separately
controlled v4 full-season experiment still has early as-of snapshot gaps,
196 missing selected-v4 horizon cells and a 32-row/26-fixture roster gap.
The completed paired control/v4 diagnostic remains unchanged.
