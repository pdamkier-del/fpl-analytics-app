# Probabilities in the existing FPL desktop app

The initial standalone GK-table delivery did not satisfy the requested existing-app integration. The correct public entry point is now:

https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/players-classic.html?mode=forecast&horizon=1

The original desktop templates, sidebar, table filters, profile hero, six-GW strip, comparison panel and My Team sheet are reused. Scoped probability components inherit the existing white cards, green values, palette and typography. Forecast-table player links open a detail dialog; the full original player profile contains the same probability panel. The existing My Team sheet retains its captain/vice/swap actions and adds the labelled B probability panel.

Read-only player/club statistics pages consume the validated role-aware B forecast, without relabelling its model contract. Private planning pages and their existing service, locked forecast identity, plan keys and manager-state contracts remain unchanged; the probability panel does not submit private jobs or alter a saved squad.

Numerical source and all sealed model outputs are unchanged from validated runtime `150695746949e5f405b3af944e4b53e2f96c2af4`, full-model run 39263489281. The UI workflow asserts the numerical-code boundary and byte-compares copied current/GK forecasts before publishing. The regular current-preview exporter now applies the same integration to subsequent fresh model runs.

UI source: `6f1b2f7694422d4502d49c01f93a56476ca7fb16`.

- All 713 Python regression tests and existing preview/private-manager JS contracts passed.
- UI validation: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39303149704
- Deployment: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39303643067
- Publication-pin-only main commit: `164b2a4781afbe225625a9f14229a8ea3880da11`.
- Desktop and mobile Chromium checks passed locally, in CI, and against the public deployed app with TLS verification. They exercise the original sidebar, forecast table, 8 probability cards, six-GW selection, full original profile and original My Team popup. No page errors, manager-state changes or private plan submissions occurred. My Team tests use an isolated synthetic browser fixture, never a real manager's data.
- Public receipt confirms all 88 production files remain byte-identical: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/publication.json

Only the isolated B app was updated. The standalone GK view remains as diagnostic evidence; it is not the desktop-app delivery link.
