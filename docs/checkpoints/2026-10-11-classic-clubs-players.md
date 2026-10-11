# Original classic Clubs and Players — 2026-10-11

Continue from branch HEAD, preserving private local manager state.

Restored the original mobile-pwa-refresh-20261009 `app/index.html` club shell and `app/rankings.html` player shell as Clubs/Players Classic. Retained tabs, pitch grouping, sortable tables and technical sidebar. Removed old FPL_DATA/demo bootstrap. The display adapter uses official current identities/season totals, original diagnostic vFinal and cutoff-matched fixture expectations only.

Column buttons toggle ascending/descending with aria-sort. Missing values remain last in either direction; real zero is preserved. Official stats and forecasts show separate source timestamps. Forecast age/deadline/GW checks mask expired values. Start probabilities are not combined into invented DGW probabilities. Clubs offer original Startchancer/Forecast/Recent Stats/Fixtures; historical 3/6-GW stats and tactical XI/subroles remain Not Available without source data. Player and club links are versioned and old bookmarks redirect to canonical pages.

No changes to MM/vFinal/TS/chip mathematics, no manager storage writes, and locked_model_active remains false. Official display exporter additionally retains native BPS and defensive_contribution fields without changing model input.

New tests cover ID joins, missing data vs zero, ascending/descending null sorting, DGW probabilities, expired forecasts and fixture cutoff mismatches. Existing JS suite passes; final Python suite and published browser checks are run before delivery. Mobile viewport/touch and genuine hourly scheduled-run proof remain the previous documented limits.
