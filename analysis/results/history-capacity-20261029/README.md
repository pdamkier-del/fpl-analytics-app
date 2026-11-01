# Automatic history capacity wait

When Render replies HTTP429 before accepting a private history job, the existing B client now shows “Venter på ledig plads” and retries automatically. Retry delays grow10/15/20/25/30seconds (bounded Retry-After is honoured), for at most30minutes. The page must stay open while waiting for acceptance. This is a browser-side wait, not a claimed server reservation. No automatic retries for validation or other HTTP failures, network failures, or already-accepted POSTs. After acceptance the original capability receipt/poll/resume/ack flow is unchanged.

Repeated clicks share one promise; controls stay disabled. The card clearly distinguishes waiting for capacity from retrieving FPL history and computing historical reviews. Existing calculations are never cancelled and personal state/plan/history remain untouched until a validated import succeeds. No backend/model/production changes or Render redeploy required.

Focused Node regression: two busy replies then one accepted job; bounded backoff; concurrent callers share one job; accepted receipt reused until acknowledgement; invalid input is not retried; permanent capacity limit ends explicitly at30minutes without falsely claiming a job started.
Desktop/mobile browser regression: real10second busy interval, visible waiting badge and automatic continuation into all15players/sixGW/old-team navigation with unchanged local state/plan. Other history failures still preserve existing archives.

Published successfully in40935501241 and verified on30October on public desktop/mobile. Subsequent scheduled model refreshes retain the exact fixed UI. Current Render capabilities/fingerprints remain correct. Public verification checks the exact two client/card source bytes and all production files against the current retained publication artifact; forecasts legitimately advanced since the original29October release. No further owner deploy or permission is required.
