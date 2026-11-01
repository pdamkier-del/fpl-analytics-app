# Desktop planner usability and actual player/club history

Initial UI source: `8bd1353c07d6541c5e7dcb13cb6fe8bdb12fe44d`. Final cache-safe UI source: `340ef9b16590a37958138c43c4b05e8335e01ef8`. The final UI reuses the numerical artifacts of full model run `39316294660` at source `8bd1353c07d6541c5e7dcb13cb6fe8bdb12fe44d`; unchanged numerical code and artifact bytes are checked again by its UI gate.

The existing B desktop app now explains manager-state problems precisely, including the reported GW 7 → GW 8 mismatch. A private confirmation dialog reuses the saved 15 IDs, purchase prices and chip history; the user confirms current bank, free transfers and actual squad. It records the actual confirmation time, validates the whole squad, saves the previous state separately, checks that another tab did not change the state, and leaves the actual state unchanged on cancellation. It does not infer FT carry-over or backdate the observation. A state newer than forecast still waits for the next verified model capture, as required by the existing original worker contract.

Plan context shows target GW, concrete validation failures, data/confirmation/computation timestamps and current computation readiness. New injury news and missing news cannot be reported as ready or as a confirmed injury.

The existing TS transfer card retains genuine manager-score totals against keeping the squad. A new explanation shows each selected outgoing/incoming player's next-GW/six-GW xP, xM and per-fixture P(start), official hit points and the existing separate uncertainty penalty. The penalty is not presented as an additional official FPL point deduction.

A manual 0/1/2-transfer comparison validates actual selling prices, budget, club limit, positions, uniqueness, official hits and next-GW FT. Its outputs are explicitly labelled sums of **player-xP differences**, not independently optimized TS alternatives or team/captain/bench scores. Existing TS versus no-transfer manager-score comparisons remain available. No separate optimizations are claimed and no actual transfer is executed.

Owned-player injury cards add the current planning forecast's xM/xP/start chances and the highest-xP other owned player in the same position. That player is not labelled a guaranteed legal autosub or a new optimized transfer recommendation. Unknown news stays unknown; no medical return date is invented.

Local plans still present under either the original production or B storage key are retained in a read-only, deduplicated archive. Legacy production plans never become current B plans automatically. This cannot recover plans previously deleted from browser storage. The user clarified that their missing data meant historical player/match statistics; the archive is separate from that correction.

## Historical player and club data

The earlier B adapter routed `match-results.json` to independently updated production history while `FplMatchData.usable` required its timestamp to equal the prospective B catalogue timestamp. Consequently existing actual history was rejected. Copied fixtures also lacked the historical FPL event payload. The fix preserves the original production components and supplies a coherent independent bundle of actual catalogue, full fixtures and match/GW results, extracted from a successful immutable production Pages artifact. All three capture times and player/fixture identities are checked, each file is hashed, and the browser verifies checksums before use. Actual data uses its own provenance rather than altering its time to match a forecast.

Only the B adapter and copied historical views are changed. Player and club model forecasts retain their original sealed input identity and contract. MM/PM/TS source, worker, risk parameters and numerical forecast artifacts are unchanged by these UI changes.

The current historical bundle has GW 1–7 and 4,474 official player match records, captured at `2026-10-19T19:28:44.289113+00:00` in production run `39310138654`, Pages artifact `12215294056`. Available data is current-season actual match history, not an invented multi-season series. Player profiles provide direct historical/results and forecast/component navigation. Club pages offer last 3/6/all played matches, league points and goals, expandable real player/point breakdowns and direct navigation to future forecasts. Historical observed stats are explicitly separated from future predictive xP; the app does not claim historical mean points alone generate a forecast.

Content-derived queries are added to all copied local JS/CSS asset URLs, including the B adapter. This prevents an existing browser from retaining the older adapter without the history API while loading a new page. The browser test verifies the adapter URL version against its actual SHA256 prefix. Historical adapters/views expire their in-memory snapshot after 60 seconds so later page refreshes can retrieve updated match data. Club pages link directly to their current roster’s last-six-GW statistics.

## Validation

- 724 Python regression tests passed locally, including preservation of actual history bytes, rejection of mixed captures, empty histories and unknown fixture IDs.
- JS checks cover exact GW diagnosis, confirmed rollout/cancel behavior, unchanged IDs/prices/chips, official selling/hit arithmetic, legacy archive deduplication, news uncertainty, independent historical adapter checksums and existing private manager contracts.
- Local Chromium desktop/mobile planner tests passed: old-GW rejection, no production-plan activation, confirmation/cancel, state backup, later-than-cutoff wait, original TS explanation, manual three-scenario table, owned injury impact, no submitted private jobs and no page errors.
- Local actual-data history browser tests passed: independent actual/forecast clocks, all available past GWs in a player profile, club past matches and player statistics, forecast navigation and no page errors.
- Existing desktop probability/My Team regression and full automatic dashboard lifecycle regression passed. Private synthetic fixtures use a real original six-GW TS result; HTTP job transport is mocked and never sends a test squad to the actual worker.

CI UI validation: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39316131265
Fresh full model validation: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39316294660
Initial UI deployment passed: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39316707215. Public desktop/mobile planner and historical-player/club browser tests passed again against that deployment, with no page errors or real private submissions. The public receipt identifies source `8bd1353c07d6541c5e7dcb13cb6fe8bdb12fe44d`, and all 88 production files remained identical. The public news feed was captured at `2026-10-19T20:05:48.361040+00:00`. Fresh-model publication and final checks follow below.

Dashboard: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/overview.html#dashboard
Players/history: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/players-classic.html?mode=recent&recent=6
Clubs: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/clubs-classic.html

## Fresh numerical output and cache-safe release

Full source `8bd1353c07d6541c5e7dcb13cb6fe8bdb12fe44d`, run `39316294660`, passed all stages, including two original source-chain replays, two complete B → locked PM runs, joint-GK historical/uncertainty/role validation and stage checks.

- Private-planning forecast: `2e481d0e593497f5d20495dce4c78152ff725db135b46958c0cf5978d2d439b5`, cutoff `2026-10-19T20:12:48.057713+00:00`, GW 8–13.
- Read-only probability forecast: `8c70f5e828b838333b27a780fb4acac680b89dfe4d17022078d7656b5b79d4a7`, cutoff `2026-10-19T20:22:17.428992+00:00`.
- Full-data publication at initial UI source 8bd1353: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39321094875
- Final cache-safe source `340ef9b16590a37958138c43c4b05e8335e01ef8` UI validation: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39321061818. This reuses the successful full model artifact, checks the unchanged numerical source boundary, reruns all Python/JS/browser checks and byte-compares the numerical forecast files. It avoids recomputing unchanged numerical code for changes to asset URLs, history refresh and navigation.

Final UI validation `39321061818` passed at source `340ef9b16590a37958138c43c4b05e8335e01ef8`: 724 Python tests, original private-manager JS contracts, new planner/history checks and all four desktop/mobile browser suites. Final deployment passed: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39321493193 (main workflow-pin commit `60306e48128710db1735787322e82861690d4832`; only the three preview publication configurations changed). Future scheduled B rebuilds and news refreshes pin the same source. No superseded scheduled preview was active when the final source was pinned.

Final public Chromium desktop/mobile planner and history checks passed against the fresh forecast. Content-hashed adapter URLs match actual fetched bytes. Confirmation/cancellation and old-state backup, legacy read-only archive, transfer explanation, manual 0/1/2 comparison, club/player history and forecast navigation all passed with no page errors. No private test job or actual transfer was submitted. A separate genuine-news read-only check displayed Haaland doubtful at 75%, all 15 synthetic owned IDs, and `can_compute`; automatic private submission was paused for that check. The final layout was visually inspected. This does not claim that the user's inaccessible browser state has been updated or that their actual personal plan was computed.

Public news capture: `2026-10-19T20:40:09.239114+00:00`. Both published forecast files were byte-compared to the successful full numerical artifact. The final public receipt identifies source `340ef9b16590a37958138c43c4b05e8335e01ef8`, and all 88 production files from run `39310138654` remained byte-identical during preview publication. Original MM, PM, TS, worker and risk parameters remain unchanged.
