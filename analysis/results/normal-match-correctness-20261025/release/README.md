# Published and publicly verified B normal-match timeline

App: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/transfers-classic.html

- Numerical source: `03d5c4d4777b44bc1d37884a1cf4dde106b45cab`.
- Reviewed UI: `bf518dd5a5aec0cbc18b49375e4afb09ec409a55`.
- Successful fresh numerical run: [40209861386](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/40209861386).
- Successful Pages/browser publication: [40212842806](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/40212842806).
- Served forecast: `28b124a5a825632707fb24aef9ee037c956dade5bed51a75ea4d10f5a80f0a81`.
- Forecast observation: 25 October, 16:23:45 UTC / 17:23:45 Copenhagen.

990 tests pass in the numerical job; the publication repeats the regression
and browser checks. The real forecast covers 669 players / 4,014 rows /
60 fixtures / six GWs. Both current numerical computations are byte identical.
One-match and one-GW scope checks and the synthetic six-GW TS search pass.
The original unchanged-head historical reference is reused through its pinned
dependency/parity proof; it is not relabelled as a new predictive improvement.

The served forecast passes the complete B contract. Actual public desktop and
mobile browsers independently check 48,000 team draws each: outfield 900,
goalkeeper 90 including the explicit unlisted-keeper pool, at most 16 modeled
participants, maximum five substitutions and maximum three live windows.
PM means equal the shared TS point-scenario means. No page errors or real
private-plan POSTs occur; normal TLS verification stays enabled. The player
audit panel also passes public desktop/mobile, stale-evidence and tampering
checks and displays the verified normal-match substitution scope.

These are planned normal-match constraints. Dismissal-driven minute truncation,
emergency-keeper reassignment, concussion exceptions and an empirical physical
to FPL-reported clock conversion remain unmodeled/unvalidated. No full physical
or individual predictive-calibration certification is claimed.

## Production isolation and the separate scheduled data refresh

Only the B publication workflow's five source/cache pins changed on `main`,
commit `601c58ce92a29acaff42d417d0f03df6c3798b28`. No production model or backend
deployment was made. Superseded old-source B publication run `40210760818` was
cancelled to avoid a later rollback of the new B model.

An existing independent scheduled production-data job
[40210669590](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/40210669590)
ran on the preceding `dbd942b...` main code at 16:13–16:25 UTC, before this B
release. It refreshed ten data files; the production model remains
`original_locked_vFinal_diagnostic`. Therefore a claim that every production
byte stayed identical from the start to the end of this entire working session
would be incorrect. This separate scheduled refresh was not triggered by the B
change.

The B publisher preserved **all 88 files** from that already published
production artifact (`12606221778`). Every actual served production file was
subsequently downloaded and its SHA-256 compared with that artifact's recorded
fingerprint; all 88 match. See `served-forecast-and-production.json` and
`production-publication.json` for the exact scope and provenance.
