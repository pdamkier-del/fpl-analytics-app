# Transfer Strategy v2 — lineup-aware replay grid

Point model is locked. Chips are OFF.

TS v2 values candidate squads by projected manager score over the horizon, not
the raw sum of all 15 players' xP. For every future GW in the horizon it jointly
selects:
- legal XI
- captain
while retaining the same 15-man squad across the horizon unless a transfer is
made at the current deadline.

This explicitly captures the case where a player has poor fixtures now but a
good later fixture and can simply be benched rather than sold and bought back.

Same nine policy/buffer combinations were rerun on recovered rolling Phase5Q
forecasts as a strategy proxy.

Results:
1. 6GW decay, buffer 1.5: 2137 pts, 54 transfers, 68 hit pts
2. 6GW decay, buffer 2.0: 2125 pts, 50 transfers, 52 hit pts
3. 6GW decay, buffer 1.0: 2090 pts, 52 transfers, 60 hit pts
4. 3GW 0.80/0.60, buffer 1.5: 2087 pts, 45 transfers, 32 hit pts
5. 3GW 0.85/0.70, buffer 2.0: 2066 pts, 46 transfers, 36 hit pts
6. 3GW 0.85/0.70, buffer 1.0: 2061 pts, 53 transfers, 64 hit pts
7. 3GW 0.80/0.60, buffer 1.0: 2056 pts, 47 transfers, 40 hit pts
8. 3GW 0.85/0.70, buffer 1.5: 2042 pts, 49 transfers, 48 hit pts
9. 3GW 0.80/0.60, buffer 2.0: 1997 pts, 43 transfers, 24 hit pts

Policy averages:
- 6GW decay: 2117.3 pts
- 3GW 0.85/0.70: 2056.3 pts
- 3GW 0.80/0.60: 2046.7 pts

Buffer averages:
- 1.5: 2088.7 pts
- 1.0: 2069.0 pts
- 2.0: 2062.7 pts

Key finding:
Once bench/starting flexibility is modeled correctly, the result reverses from
TS v1. The longer 6GW horizon becomes clearly superior. This is consistent with
the intended behavior: TS v2 can retain future-value players through bad near
fixtures and bench them instead of transferring them out.

Recommended TS v2 proxy:
- primary: 6GW decay (1.00,0.85,0.70,0.55,0.40,0.25), hit buffer 1.5
- conservative sensitivity: same horizon, buffer 2.0

Caveat:
This remains a strategy proxy using recovered rolling Phase5Q forecasts, not the
final vFinal full-season result. Repeat unchanged TS v2 on cutoff-safe rolling
vFinal forecasts.
