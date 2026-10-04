# Predeadline source located; freeze acquisition selection

Continues `bc19969975fd2b24d9a5fccbd4de819b77ad0323`.
The original Library data audit identified Randdalf/fplcache as a bootstrap
snapshot source. Its current pinned tree contains predeadline snapshots for
all 17 diagnostic GWs (22–38). The latest path before each frozen cutoff was
selected, and the file's Git commit history independently confirms publication
before that cutoff. Source blob SHA, commit SHA and publication time are frozen
in `analysis/results/joint-deadline-snapshot-selection-v1/selection.json`.

`scripts/recover_joint_deadline_snapshots.py` downloads immutable commit URLs,
verifies original blob SHA and size, preserves raw XZ bytes in checksummed
parts, and checks each official event deadline against the frozen v4 cutoff.
It validates season-specific element IDs against stable FPL codes before
projecting nullable player states. No Core data or prior experiment is changed.

This resolves source discovery, not yet all missing forecasts: the next step
is byte recovery and a per-row comparison against actual predeadline FPL
listing/team/position. Snapshot presence is not proof of matchday fitness.
Transfer/chip policy and the old control/v4 comparison remain unchanged.
