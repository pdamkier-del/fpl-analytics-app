# 9-way transfer strategy grid — chips off

Compared 3 forecast-horizon policies x 3 hit uncertainty buffers on the recovered
rolling Phase5Q archive. This is a strategy proxy, not a vFinal full-season
performance result.

Policies:
- 3GW (1.00,0.85,0.70)
- 3GW stronger decay (1.00,0.80,0.60)
- 6GW (1.00,0.85,0.70,0.55,0.40,0.25)

Buffers:
- 1.0
- 1.5
- 2.0

Best replay:
- 3GW (1.00,0.80,0.60)
- hit buffer 2.0
- 2109 points
- 54 transfers
- 72 hit points
- uplift vs no-transfer control +684

Second:
- 3GW (1.00,0.85,0.70), buffer 2.0
- 2093 points
- 59 transfers
- 92 hit points

Policy robustness averaged across buffers:
- 3GW 0.80/0.60: 2090.3 points, 94.7 hit points, 60 transfers
- 3GW 0.85/0.70: 2074.3 points, 108.0 hit points, 63 transfers
- 6GW decay: 2058.0 points, 134.7 hit points, 70 transfers

Buffer robustness averaged across policies:
- buffer 2.0: 2081.3 points, 93.3 hits, 59.3 transfers
- buffer 1.0: 2073.7 points, 128.0 hits, 68.7 transfers
- buffer 1.5: 2067.7 points, 116.0 hits, 65.0 transfers

Interpretation:
- 3GW stronger decay is the strongest and most robust of the tested horizon policies.
- buffer 2.0 is the strongest overall and materially suppresses unnecessary hits.
- 6GW creates too many transfers/hits and underperforms.
- recommended vFinal primary replay strategy: 3GW (1.00,0.80,0.60), hit buffer 2.0.
- retain 3GW (1.00,0.85,0.70), buffer 2.0 as sensitivity comparator.
