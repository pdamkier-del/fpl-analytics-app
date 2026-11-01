# Existing desktop transfer workspace

Source: `51488f30d18ff8a9b57fb5c481486c1b42b6b822` on the existing PR #22 branch. This is a presentation change in the existing B desktop app, not a new app or production template change.

The transfer page now has a primary compute action, a direct action opening manual alternatives, a saved-squad/bank/FT strip, a single ready-state indicator, and a prominent recommendation with existing outgoing/incoming players, official hits and next/six-GW net xP gains. Recommendations to keep the squad remain supported. Original model explanations and no-transfer comparisons are preserved.

The original recommended XI/captain/bench, six-GW decision path and chips render inside keyboard-accessible native disclosures. Player xP/minutes/start chances and model uncertainty have their own disclosure. Manual one-transfer exploration and the existing 0/1/2-transfer comparison are grouped in one collapsible area. This avoids showing all large tables and the pitch immediately. Model fields and equations, private service endpoints, saved squad, purchase prices, FT rules and risk parameters are unchanged. Ready-state duplicate messages are hidden; waiting/error/progress feedback remains visible.

`integrate_transfers_workspace.py` replaces only the generated B copy of the transfer HTML and chooses the preview-only renderer and stylesheet. Root production files are untouched. All new local assets receive the existing content hashes to avoid stale browser caches. Existing sidebar, desktop palette and mobile navigation are retained.

Local verification:

- 724 Python regression tests passed.
- Planner JS contract checks passed with the existing private synthetic original-TS fixture.
- Chromium desktop (1440px) and mobile (390px) tests passed: precise GW validation, confirmation/cancellation and state backup, waiting for a newer forecast, read-only archived plans, unchanged actual squad and original net xP gain, initially collapsed plan sections, successful opening of XI/path/chips, no horizontal viewport overflow, direct opening of alternatives, manual 0/1/2 comparisons and dashboard news impact.
- No page errors or real private job submissions. Both viewport screenshots inspected.

The numerical artifact is reused from successful full six-GW validation run `39316294660`, source `8bd1353c07d6541c5e7dcb13cb6fe8bdb12fe44d`. CI independently checks the numerical source boundary and byte-compares the forecast artifacts, while rerunning all regression and desktop/mobile suites. This UI change does not claim a fresh numerical model run or a personal plan for the user's inaccessible browser state.

CI UI validation passed: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39417684724. It reran 724 Python tests, original manager/adapter/distribution/news JS checks and all four browser suites. The browser evidence includes unchanged net xP, working collapsed sections and desktop/mobile overflow checks.

Deployment passed: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39418348274. Main commit `35d464e7be7a8b4d96d7932a3d23c7d3944daf80` changes only the three B preview publication source pins. Hourly B rebuilds and news refreshes retain this UI source.

The public receipt identifies the exact UI source above, production run `39404946060`, artifact `12256977471`, and all 88 production files identical. Both public forecast files were byte-compared with the validated numerical artifact. This deployment reuses the previously validated forecast and does not change MM/PM/TS.

Public app: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/transfers-classic.html?release=51488f3


Post-deployment public Chromium verification passed for desktop and mobile with no page errors and no real private submissions. Exact GW diagnosis, state confirmation/cancel/backup, original TS net gain, disclosures, manual comparisons and dashboard impact all passed again. An additional public mobile check without any private state confirmed the import path, usable alternatives disclosure, no invented squad, no POST requests and no horizontal overflow.
