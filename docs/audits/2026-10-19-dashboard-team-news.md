# Dashboard: private squad news and next-GW readiness

The existing FPL desktop dashboard now displays official availability news only for IDs in the browser's saved actual squad. It distinguishes doubtful, injured, suspended, unavailable and available states, displays the original FPL wording, availability percentage and `news_added`, and separately identifies capture time. Missing publication times remain unknown. FPL availability is explicitly distinguished from the model's P(start).

A lightweight public collector is scheduled to capture the official FPL bootstrap every 15 minutes (GitHub scheduling is best effort) through a separate Pages workflow. The feed contains the public player catalogue, never a manager's squad. Its schema, source URL, content hash, deadline, identities and timestamps are checked; data over one hour old fails closed. The browser refreshes through the app's existing five-minute load cycle and offers a manual refresh.

The news-only publisher restores the actually deployed B preview from the live branch and changes only its public news file. It preserves the current UI/model provenance and verifies every pre-existing non-news preview file. The normal UI/model publisher retains the freshest verified news to prevent a model publication from rolling the news feed backwards. Both use the existing publication concurrency lock and preserve all production files.

## Personal proposals

The next target is the next official GW, not an inferred calendar week or a fabricated future manager state. The original MM/PM/TS code, risk parameters and private worker remain unchanged. Original private job IDs, forecast/state signatures and idempotent retries are reused.

The dashboard distinguishes: missing actual squad, missing/stale news, manager-state update required, newer news awaiting a matching model, calculation in progress, ready to calculate, and completed/current proposal. A proposal is shown as ready only when its existing validated private result matches the forecast and the official availability catalogue still agrees with the snapshot used by that forecast. All candidate-player availability/price/team/position changes are checked, so a newly unavailable transfer target cannot silently remain eligible in an old optimization. New news during an in-flight job is checked again before accepting the result. The existing My Team/transfer calculation client receives the same news gate.

Automatic calculation is enabled by default on the dashboard, can be paused locally, and runs only with a legal actual manager state and current matching inputs. Pending jobs, recent attempts, completed matching plans, unavailable data and unrelated routes suppress new automatic submissions. Repeated refreshes do not resubmit a completed plan. No captain, lineup, squad, bank, FT or transfer is changed by this feature.

Automation runs while the dashboard is open. Public news and forecasts can refresh while it is closed, but the implementation does not promise a new personal computation while no browser is running, does not persist a private squad in a new backend, and does not infer next-GW bank/FT/chip state. Missing actual information is requested through the existing manager editor.

## Validation

- Source: `652f88c62f6392a514ea7d349b06d6f121538e93`.
- All 720 Python regression tests passed, plus the new JS availability/readiness/deduplication checks and existing preview/private-manager contracts.
- UI validation: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39307888211
- Initial UI deployment: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39308433016
- News-only refresh: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39308693191 — all 121 existing non-news preview files preserved, with UI provenance unchanged.
- Local, CI and public desktop/mobile browser tests passed. A private synthetic legal 15-player fixture uses an actual original six-GW TS result with mocked HTTP transport; no test squad is sent to the real private service. The browser tests verify doubtful status, stale-news/model blocking, exactly one automatic job, display of the completed TS result, no duplicate on refresh, invalidation after a later injury update, no page errors and byte-identical actual manager state.
- A separate public read-only test uses the genuine published FPL news feed with automatic computation paused. Haaland's actual FPL status was doubtful, 75% chance of playing, with the original unspecified-injury wording and 19 October 13:00 UTC news time. No actual personal plan is claimed for the user's inaccessible browser state.
- Existing private service health was checked: original locked Python runtime ready, MM preview and idempotent submit supported.

## Current data and publication

Complete fresh model run: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39307888361 — passed. The original source chain and six-GW B → locked PM outputs were reproduced twice, and joint-GK historical/uncertainty/role/stage checks passed. All 668 players and 60 fixtures cover GW 8–13.

Private-planning forecast: `64b13835fd8d7b755e73bbc66f9ea10c3982b53d432cabf17d0ed97ba8e74f23`, cutoff `2026-10-19T19:09:16.653816+00:00`. Read-only probability forecast: `6056dd5f473d45008dfd2adf6d0d5ab5ed7d4657e779fd61698e5e5886163c49`, cutoff `2026-10-19T19:14:22.522266+00:00`.

Fresh-data deployment: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39310564792 — passed. Both published forecast files were byte-compared to the successful validation artifact. The publisher preserved all 88 production files from the concurrently completed scheduled production-data run `39310138654`. The freshest previously verified news feed was retained.

Final public Chromium desktop/mobile tests passed again with the fresh forecast and newly computed original TS fixture: exactly one job, actual six-GW result displayed, duplicate prevented, later injury invalidation, unchanged state and no page errors. The separate genuine-feed read-only browser test showed `can_compute` rather than `waiting_forecast`, all 15 owned IDs, and Haaland doubtful at 75%; no real private job was submitted by that check. The final layout was visually inspected.

App entry: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/overview.html#dashboard
