# Completed: full all-club MM replay and diagnostics

Branch research-role-injury-club-audit-20261016; PR #8. Start from current HEAD, not an older framework checkpoint.

All 40 evaluation club-seasons and 20 earlier development club-slices have completed. Nine arms (five requested + isolated role-duration/full-return alternatives), 540 club/model/phase records, 5,400 largest-error cases. Complete club metrics, player groups, source-selection return matches1–3 (scheduled and actually played separately), false zeros, paired calendar-GW-block intervals, and specific City/Chelsea/Arsenal/Liverpool reports.

Read docs/research/2026-10-16-mm-all-clubs-results.md and both per-season club reports. Scripts: validate_mm_all_clubs.py and report_mm_all_clubs.py. Input capsule reused; no PM, points, TS or chips simulated. locked_model_active=false.

Combined evaluation (39,264 rows): locked minute-MAE11.240711 → frozen chance+retur-s10.521392, delta-0.719320 [−0.889,−0.604]. All40clubs improve in point MAE estimates vs locked baseline; not every club interval excludes0. No independent holdout exists. All-player role-duration replacement worsens MAE but improves RMSE; do not call it a universal improvement.

CI38929682699 passed 46 relevant tests, all coverage/hash checks, immutable forecast check and unchanged production src. Source code297d0f4; durable data commitbd1ee8a. Seven data output contents match local replay exactly (decompress gzip before content comparison). reproduction.json records verification.

Fixture-scoped suspension correction and clinical/training-return intervention remain Not Available as certified A/B arms: the stored FPL text lacks a verified complete match-expiry mapping. Liverpool/Palace articles confirm the three DGW mechanisms retrospectively but are postdeadline and never model inputs. No years, clearance dates, injuries or tactical causes invented. GW1–5 lack frozen MM forecasts; inherited actual-outcome publication clocks remain +3/4h proxies.
