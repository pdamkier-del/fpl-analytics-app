FPL Analytics Desktop v1.6
==========================

THIS IS THE LAST MANUAL UPDATE PACKAGE.
After v1.6 is installed, Start FPL App checks the project's public GitHub repository before opening.

AUTO UPDATE CHANNELS
- App version: UI, pages, Python model code and server code.
- Data version: current FPL players, completed-GW actuals, fixtures and forecast snapshot.
- App and data are versioned separately, so a weekly data refresh does not require reinstalling the app.

PRESERVED LOCAL STATE
Automatic updates do NOT overwrite:
- user/ (including your 15-player squad)
- model/active.json
- model/versions/
- model/runs/
- runtime/

REMOTE SOURCE
https://github.com/pdamkier-del/fpl-analytics-app

CURRENT DATA
- 562 players
- 3,250 player-GW actual rows through GW5
- 380 fixtures
- GW6-GW11 forecast snapshot

INSTALL ONCE
1. Extract this ZIP.
2. Double-click Install FPL Website.bat.
3. From then on, start the app through the FPL Analytics desktop shortcut.
4. On startup the black window will briefly show the app/data update check, then the browser opens.
5. If GitHub is unavailable, the current local version still opens normally.
