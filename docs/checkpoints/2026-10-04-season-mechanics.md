# Isolated 2025/26 transfer and chip bookkeeping

Continues cd0e01a424b0fd2fae6c3e1cb5e2f02f28f5c163. 125 tests pass, including eight meaningful seasonal boundary/state tests. The original three transfer/chip policy hashes remain identical to 8091c857ccc9909637e4884212f534834b9576ac. Original paired forecasts, scoring, simulator and adapter are untouched.

`src/fpl_xpts/season_2025_26_rules.py` supplies an opt-in deterministic legality/accounting layer. It does not select transfers or chips and is not imported by the archived policy. It covers GW16's top-up to five (not addition), ordinary capped rollover/hit costs, WC/FH preservation without additional FT accrual, opening-GW unlimited transfers/no WC or FH, the two chip windows, one chip per GW and the FH19/FH20 restriction. Tests include the GW15-to-GW16 chip boundary, transfer overspend, cap, invalid histories and final deadline.

Source URLs, source publication dates, exact code checksums and test verification are in `analysis/results/season-2025-26-mechanics-v1/verification.json`. The May 2026 live FAQ gives a conflicting absolute GW19 clock time versus the season announcement; this layer uses GW indices and does not consume that clock time. Existing source snapshots remain the deadline evidence. It applies only to a manager entered before GW1, not late-entry managers.

This removes an unimplemented unit-level mechanics task, not the integration gate. Full-season orchestration must explicitly apply the profile identically in control and v4 and preserve the restored strategy. Historical scoring, roster gaps, full preseason/rolling-origin forecast coverage, prices and as-of schedules still gate a season replay.

Independent source check: Brentford's 11 January 2026 signing announcement confirms Furo's club and forward role before GW22, subject to clearance/work permit. It does not confirm FPL element availability/classification or complete eligibility, so no blocked row was promoted. Source: https://www.brentfordfc.com/en/news/first-team-brentford-sign-kaye-furo-club-brugge .
