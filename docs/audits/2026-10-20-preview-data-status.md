# Compact preview status and preserved model freshness

The large yellow preview banner exposed internal model names, a raw ISO cutoff and an unavailable interval warning across every desktop page. It is replaced with a compact neutral `B-preview` marker and native `Om data` disclosure. The disclosure retains actual capture time formatted in Danish/Copenhagen time, private-state/no-transfer information and the existing model limitations. Data-loading failures automatically open the disclosure rather than hiding an error. No probability or numerical model changes are made.

During this work we found that UI-only validation reused the October 19 numerical artifact even though a successful scheduled October 20 full build existed. Publishing the UI therefore rolled the B forecast back. This could make recently confirmed squads wait unnecessarily under the legitimate observation-before-forecast worker rule. The UI gate now reuses full scheduled run `39405073005`, whose immutable workflow source pin is independently checked: main head `60306e48128710db1735787322e82861690d4832`, actual model source `340ef9b16590a37958138c43c4b05e8335e01ef8`. The private forecast is captured at `2026-10-20T10:07:05.576688+00:00`.

The preview publisher now checks the actually served private and public-probability forecast timestamps before modifying publication state. It refuses an older incoming forecast in either branch, fails on network/invalid timestamp errors, and permits equal/newer snapshots. First publication is permitted for HTTP 404 only. Four regression cases cover private/public rollback rejection and equal/newer acceptance. UI changes can no longer silently replace newer B model data with older validated artifacts. Production preservation checks remain in place.

A manager confirmation later than the newest forecast still correctly waits; this fix does not backdate state, relax validation or claim a personal calculation for inaccessible user browser storage. The user should confirm actual squad/bank/FT only when necessary, then press the green calculate button. If the forecast is older, the existing client queues calculation while the page remains open. Reconfirming unchanged state repeatedly would reset its actual observation time and prolong waiting.

Final UI source: `b82f7345f31a948dcb1dbc925aca701e9388604a`.

- UI CI passed: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39420195662 (728 Python tests, unchanged numerical code/artifact checks, existing JS contracts and all four desktop/mobile browser suites).
- Deployment passed: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39420638203. Main publication pin `24312c9ae87587f4d7df5f588fc66da77661f938` updates only the three B preview publication configurations.
- Public Chromium desktop/mobile checks passed: marker under 60px, details initially closed, clickable data disclosure with actual Danish/Copenhagen time and retained limitations, no page errors, no horizontal overflow and no private submissions.
- Both public forecasts match full scheduled run `39405073005` byte-for-byte. Planning capture: 20 October 12:07 Copenhagen time; probability capture: 20 October 12:12. No fresh numerical recomputation is claimed for this UI release.
- The publication receipt identifies exact source b82f734 and all 88 production files unchanged.

App: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/transfers-classic.html?release=b82f734


The complete public desktop/mobile planner suite also passed again against the October 20 fixture: exact state diagnosis, confirmation/cancel/backup, unchanged original TS gains, all disclosure controls, manual comparisons, no real private submissions and no page errors.
