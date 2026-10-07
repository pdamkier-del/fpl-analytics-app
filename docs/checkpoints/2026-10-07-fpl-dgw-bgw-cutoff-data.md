# Cutoff-safe FPL DGW/BGW knowledge — 2024/25

Purpose: historical replay input for when a Double/Blank Gameweek was officially knowable.

Rules:
- `knowledge_date` is the publication date of the official Premier League/FPL announcement.
- `first_safe_cutoff_gw` is deliberately conservative: the first FPL deadline after the dated announcement for which the information can be used without hindsight leakage.
- Before that cutoff, the concrete DGW/BGW must not be injected into TS/TC forecasts.
- Once the safe cutoff is reached, the confirmed schedule is treated as ordinary future fixture information.
- This file records confirmed schedule knowledge only. Probabilistic/latent future-DGW value belongs in the separate latent-DGW prior and must not double-count confirmed fixtures.

Confirmed 2024/25 schedule events captured here:
- DGW24: Liverpool, Everton — announced 17 Jan 2025.
- DGW25: Liverpool, Aston Villa — announced 7 Feb 2025.
- BGW29: Liverpool, Aston Villa, Newcastle United, Crystal Palace — known from the EFL Cup-final schedule on 7 Feb 2025.
- DGW32: Newcastle United, Crystal Palace — announced 14 Feb 2025.
- DGW33: Arsenal, Aston Villa, Crystal Palace, Manchester City — announced 3 Apr 2025.
- BGW34: Arsenal, Aston Villa, Crystal Palace, Manchester City — confirmed with the DGW33 rescheduling on 3 Apr 2025.

Primary sources are the official Premier League Fantasy articles stored in the CSV.
