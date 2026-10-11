# Daily operation — 2026-10-11

The private original Python manager and the public diagnostic forecast remain separate. No personal squad, purchase prices, state receipt or recommendations belong in this repository.

## Operational changes

- Hourly source capture remains at UTC :17 on default main. The equivalent explicit 0–23 hour range re-registers the schedule. Trigger type and schedule are retained in the public attempt receipt. A successful push run is not evidence of successful hourly delivery.
- Main’s legacy daily publisher was discovered deploying a bridge without generated fixture expectations/TC assets and cancelling the proper Pages workflow. Its automatic schedule has been retired. Manual legacy invocation delegates to the canonical original forecast workflow.
- Canonical forecast and working-branch Pages deployments share one publication lock. A queued build must match the current branch’s verified cutoff, GWs and checksums before it may deploy. Artifact names include both run ID and attempt.
- Forecast failure and missed updates are visible in the weekly app and state editor. Independent raw attempt receipts remain available even when Pages publication fails. Deadline/GW and maximum forecast age remain hard guards. New-cutoff results invalidate old private plans without deleting owned players or purchase prices.
- Private submissions are idempotent: browser-generated random capabilities are stored before POST, so a lost response can resume the same state/cutoff-bound job without spawning another worker. Portable links cannot overwrite newer local state or an already-valid private plan.
- Network timeouts/disconnects retain the private resumable job. A completed result is rejected when the forecast/state changes or the forecast expires. A corrupt saved plan no longer hides the independently saved state.
- At GW rollover the editor restores old verified inputs as an unconfirmed draft, preserving GW/time/FT rather than inventing updated values. Saving clears the older draft.
- Private backend verifies fresh official GW/deadline before and after original computation, and rejects a changed public cutoff before returning the result. Health exposes an adapter digest. Worker timeouts and unavailable official sources return safe distinct messages; personal subprocess output remains suppressed and temporary inputs are removed.
- Render deployment is deliberate for relevant backend changes; forecast and UI commits do not restart personal computations. Source files under src/, config/ and frozen analysis/ are unchanged.

## Evidence

417 Python regression tests passed locally after the publication guard. JavaScript checks cover overdue/failed attempts, :17 scheduling display, disconnects, timeout, stale results, corrupt plans, private backup integrity and honest GW rollover. Fresh source pipeline 38144490282 passed the original chain, exact raw reproduction and Pages publication. It was a push-triggered run, not a verified :17 schedule.

## Certification limits

The individual 334-row BPS ledger and three historical registered-club conflicts remain unresolved; 34 additional rejected players have no archived registration. Exact provider publication times remain unverified, and kickoff + four hours is still an explicitly uncertified proxy. No replay of the same 223 provider revisions was performed.

The current StatsBomb primary competition inventory was independently fetched again on 2026-10-11: SHA256 e6cd42f5d8956d6aa30fb917ce8d4c3b3df1879a93f02f8feba820930a6971fa. It lists Premier League seasons 2003/2004 and 2015/2016 and no 2026 coverage. It supplies no repair for the missing current-season actions.

Original FH/WC/BB are rolling stopping decisions, not a fixed future calendar. Only model-supported TC concrete options may be shown, and TC remains manual. Missing future chip weeks remain Not Available. Full live certification remains blocked; locked_model_active=false.
