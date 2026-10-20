# Concrete transfer-plan blockers

The user still saw the generic waiting message after the primary action changed. That action change did not resolve invalid state or a confirmation later than the forecast. The screenshot alone does not identify which private browser-state field is responsible. The exact text from the user's existing status panel was requested; the private state cannot be read remotely.

A genuine presentation defect was found: `stateValid` includes both actual squad validation and the observation-before-forecast gate. The transfer renderer labelled every false result “Bekræft dit hold”, even when the actual squad was valid and the only blocker was its newer observation. This could encourage repeated confirmation and prolong the wait.

Preview-only copied manager feedback now provides a concrete reason from full existing state diagnosis, actual confirmation/model timestamps, original forecast-window validation or verified news alignment. Valid state newer than the forecast explicitly says to wait for newer model data and not reconfirm. The transfer status distinguishes missing/invalid actual information from a valid newer observation. Generic manager-state/cutoff instructions are replaced with the specific reason in waiting feedback; the title says the calculation has not started. Original MM/PM/TS, worker gates and actual saved inputs are unchanged.

Browser regression covers both GW mismatch (exact saved/target GW in feedback) and newly confirmed state (model-wait status and no false reconfirmation instruction). Existing valid-plan display and missing-plan single-job tests remain enabled.

This fixes misleading status, not the user's unidentified private-state blocker. No personal plan completion is claimed without the necessary status input.


UI source: `65ab05201212e81be82bed59d0fef788fd8a78d0`. CI passed: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39423484271 (728 Python regressions, existing JS contracts and four desktop/mobile suites). Deployment passed: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39424108352. Main publication pin `caec8301f2273bd8bdae6273159778f0f6e28841` changes only three B preview publication configurations. Public receipt identifies the exact source and all 88 production files unchanged. Both numerical forecasts remain byte-identical to successful full scheduled run `39405073005`.

App: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/transfers-classic.html?release=65ab052

Post-deployment Chromium verification passed on desktop and mobile: exact GW errors in waiting feedback, valid newer-state timestamps explained without another confirmation instruction, preserved actual state and TS gains, green action cache refresh/existing-plan display and single mocked missing-plan job. No page errors or real private submissions. The actual user blocker remains awaiting the requested private status text.
