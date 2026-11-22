## Existing app + B MM — diagnostic preview, not production activation

Final integration source: `41161e4521a371bc4d0ddd94e2ed6d9dda13e6e1`. Main publication/scheduler pin: `730a29dceb35fa6ca7ccc18b8d125f34209b64cb`.

### Minimal changes
- Reuse existing classic My Team, Transfers, Players, Clubs, Fixtures, player profile, Dashboard, Chips and Model pages under `mm-preview/app/`; no redesign or new model.
- Checksum-verified adapter reads one sealed B/locked-PM forecast. Exact official bootstrap/fixture fields and existing selected XI are translated into the old display contracts. Source fetch clocks remain distinct; common snapshot identity is verified.
- B's sealed snapshot SHA replaces the old renderer's raw-file checksum contract. Tested through the actual existing XI renderer for all20 clubs using the public current B snapshot: each displayed XI has11 players and1GK. Wrong snapshot is rejected. Weighted role shares are not invented raw start counts.
- Actual manager-state/purchase prices keep their original browser storage key. B plans/jobs have separate keys; existing private Python `/preview/plans` route, stale-state/forecast invalidation, failed-job recovery and compatible resumable jobs. No official FPL account synchronization/transfers, no private public artifacts.
- PM Gaussian minute sampling, PM mathematics, original TS v3/chips and production files unchanged. MM xM and PM analytic E[min] displayed separately; unvalidated quantitative intervals unavailable; `locked_model_active=false`.

### Tests
Local full suite:684 passed,0failed. New adapter:8 checks; existing B checks:28. Existing manager regression also passed against generated B app (private-state persistence, purchase-price invalidation, expiry, validation-result rejection, private restore). Classic pitch/profile/fixtures and new-GW draft tests passed. Public backend health confirms original_locked_python + supports_mm_preview; unchanged worker SHA7052cca70717dc7b7370617e973c02b59a0df2b954ee269beecefa9f114357a7.

Final current-data CI: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39129816821 . **Success:684 Python tests +36 JS checks**, feature parity, exact raw rebuilds, B→locked PM one match(66 rows), one GW(667 rows), six GW(4002 rows/60fixtures), two byte-identical full forecast/MM outputs and protected-code diff clean. Exact-source Pages publisher: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39129820245 . **Pages success**, persisted940ddb1; all88 current non-preview production artifact files byte-identical. Published cutoff2026-10-18T13:08:01.101996Z, GW8–13; forecastSHA c77e040bbe29ffdf0130faac94e10c6c59e123298925b4494b9c01bf34f109f8.

Previously verified scheduled refresh39121554563:667players,60fixtures,4002player-fixture rows,GW8–13,cutoff2026-10-18T11:09:19.599429Z. Schedule remains17 * * * *, best-effort GitHub launch timing.

### Remaining certification/personal gates
Independent validation and historical source/BPS gaps remain; production B is not activated. Actual personal output requires the user's confirmed current state in their own browser; archived GW7 state is not silently promoted to GW8. No synthetic squad is presented as the user's team.

Earlier final private deployed validation DID complete against forecast ee42561d8b599f7d02b772e7583e5973ed18faeef9f2add0dbf85ee553996eb4:6legal TS actions/XIs, official hits, FT rollover, budgets, frozen weights/buffer, provenance and all667-identity app renderer passed. No full private result/capability/squad was committed. Original2125-point historical benchmark is preserved, not newly achieved.

### Published existing app
https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/my-team-classic.html?ui=fef499563f07e0c1

Browser verified: all classic navigation routes, Players search/forecast-horizon/profile, Chelsea B XI, fixtures, My Team/Transfers/Chips missing-manager states and Model Explorer. No app JS errors observed. Haaland GW8:82.88xM,79.69 PM E[min],96.3% appearance,5.74xP; six-GW33.57. Not a retrospective accuracy claim.

Remaining display limitations: team-goal fields are unavailable until their existing expectation fields are exported at the B snapshot; per-match history requires a matching display snapshot. Old forecasts are not mixed in to hide missing data. Original model tree is retained as reference, not a new certified B-calibration explanation. Physical mobile interaction and actual current user's manager calculation were not verified in this browser. Production remains unchanged and not B-activated.

Latest resume checkpoint: `49b5a82976a264da51624bac98990d371116a488` (documentation only; executable/source pin stays41161e4).

