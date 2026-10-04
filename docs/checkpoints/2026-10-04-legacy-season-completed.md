# Legacy technical season replay completed

Continues verified GitHub HEAD `42c868fb1f99347e3eabf690d27a7158e4228b7f`.
The user explicitly requested completion of the simulation. All 38 GWs of
the available Phase 5Y legacy replay were executed with original frozen
Phase 5Q forecasts and unchanged simple_3gw transfers, joint_sequence chips,
two-point hit buffer and existing manual chip weeks. This is a technical
reproduction, not full v4 season performance.

Net points: **2,096**; gross: 2,152; hits: 56; transfers: 50.
No-transfer initial-squad control: 1,367; final bank: £1.5m.
Chips: WC GW3/28; FH GW2/36; BB GW4/31; TC GW13/33.

All 38 gameweek rows and 570 lineup rows match the archive after normalizing
two archived autosub IDs from float-text to integer-text. All 38 scores and
autosubs were recomputed from historical actuals; position counts, club
limits, bank, cumulative points and hits pass. Existing tests: 125 passed.
Protected policy hashes unchanged. No fitting or policy tuning occurred.

Checkpoints were published after GW5, GW19 and GW30. The original runner is
preserved byte-for-byte. The isolated launcher omits only unused analytic
cold-start imports; phase5q reads frozen outputs. An unused rolling_predictions
CSV contains its header only. The first extension replayed GW1–5 identically
because the archive defaults resume off; the launcher now enables resume
explicitly, and later stages resumed at GW20/GW31.

Original merged_gw and players_raw bytes were fetched from fixed Vaastav
commit `9779cdbc0c07f6c900c2d0c181ddf6bb9c800f88`. SHA256 matches the
historical Core manifest. Individual weekly files differed and were rejected.
Exact inputs are stored as checksum-verified gzip parts; forecasts reuse
the existing lossless recovery. The launcher reconstructs its scratch
runtime and resumes saved state even after scratch loss.

Outputs: `analysis/results/legacy-season-technical-replay-v1/`.
Run: `PYTHONPATH=src python scripts/run_legacy_season_technical_replay.py`.
Check: `PYTHONPATH=src python scripts/check_legacy_season_technical_replay.py`.

Limitations: retrospective same-GW roster/prices, final fixture schedule,
inherited WC/FH free-transfer accrual and missing GW16 top-up. The separately
audited 2025/26 mechanics profile is not activated in this reproduction.
The original summary's temporal-validation wording is retained as raw runner
output only: GW22–38 is reused diagnostic, never a new holdout. The 196
missing selected-v4 horizon cells and early as-of snapshot gaps are not filled.
The existing paired control/v4 diagnostic, joint simulator and adapter remain
unchanged. This requested legacy simulation is complete; a rules-aligned v4
full-season experiment still needs verified as-of inputs and separately
controlled mechanics integration.
