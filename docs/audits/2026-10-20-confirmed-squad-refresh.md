# Refresh after a confirmed private squad

The user supplied the exact diagnostic: actual squad confirmed on 20 October 2026 at 14:45:34 Copenhagen time, while the planning forecast was captured at 12:07:05 Copenhagen time. The blocker is therefore the existing observation-before-forecast gate, not a running private calculation. This resolves the previously missing diagnostic input; no actual private IDs, purchase prices or chip history were requested or inferred.

A full existing B refresh was dispatched on main (`caec8301f2273bd8bdae6273159778f0f6e28841`), pinned to validated application source `65ab05201212e81be82bed59d0fef788fd8a78d0`: run `39425077877`. It preserves the existing MM/PM/TS math and worker validation, fetches official data after the reported confirmation, reruns numerical/historical/privacy checks and publishes only the B preview over verified production files. The private state is not backdated or reconfirmed.

The earlier generic-message and green-button fixes did not themselves remove this time gate. A personal plan is not claimed computed in the user's inaccessible browser. After the new forecast is published, the existing open-page queue can resume, or the user can press the green latest-plan action without reconfirming.


Full refresh and publication passed: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39425077877. All 728 Python regressions passed. Original source-chain replay and complete B → locked PM ran twice; joint-GK repeat, stage and historical role acceptance checks passed. Output covers 668 players, 60 fixtures and GW 8–13.

- Planning capture: `2026-10-20T12:55:47.279105+00:00` = **14:55:47 Copenhagen**, later than the reported confirmation at **14:45:34**. Canonical forecast hash: `94167fc80ac3bdf063477a5abd507c764eb88258ee4b51d1c98720709c76a550`.
- Probability capture: `2026-10-20T13:05:17.793611+00:00` = **15:05:17 Copenhagen**. Canonical hash: `8f424471be3a6001d2c40737a9aabde1dc84849ed1ccba098133476fa3b324f3`.
- Fresh news publication passed: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39430040739. Capture `2026-10-20T13:24:20.651190+00:00` = **15:24:20 Copenhagen**. Its checksum and all 668 candidate identities/prices/status/news fields match the new planning snapshot. News-only publication preserved both numerical files byte-for-byte.

Public Chromium verified the exact reported confirmation time in an otherwise valid synthetic local squad: `state_valid=true`, `usable=true`, no repeat-confirmation/model-time blocker, real news accepted, and actual calculation-service health reachable from the browser with preview/idempotency support. Local state remained unchanged and no test state was sent to the actual worker. This demonstrates removal of the reported time gate; it does not claim the inaccessible actual user's personal job has completed.

The full public desktop/mobile planner suite passed again: exact diagnosis, confirmation/cancel/backup, original net xP, all disclosures, green-button model refresh and valid cached-plan display, one mocked original six-GW job for a missing plan despite duplicate clicks, manual comparisons and dashboard impact. No page errors or actual private test submissions occurred.

The public receipt identifies application source `65ab05201212e81be82bed59d0fef788fd8a78d0` and all 88 production files unchanged. Both public forecast files match this successful full model artifact byte-for-byte.

For a future UI-only gate, the newest validated numerical artifact is now run `39425077877`, wrapper head `caec8301f2273bd8bdae6273159778f0f6e28841`, actual source `65ab05201212e81be82bed59d0fef788fd8a78d0`, path `.github/workflows/mm-current-preview-publication.yml`. Do not reuse the older October 20 10:07 UTC or October 19 artifact over this newer served forecast; the publisher rejects that rollback.

App: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/transfers-classic.html?release=65ab052&refresh=20261020-1445
