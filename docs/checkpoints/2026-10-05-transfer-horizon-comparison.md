# Transfer horizon comparison — chips off

Strategy-only comparison using the recovered rolling Phase5Q full-season forecast archive.
This is used as a proxy to choose the transfer horizon before regenerating cutoff-safe
vFinal rolling forecasts. It is NOT a vFinal full-season score.

Same transfer mechanics in all arms:
- chips OFF
- hit = 4 points
- hit uncertainty buffer = 2.0 points
- saved free-transfer option value = 2.16 points

Results:
- 3GW equal (1.00,1.00,1.00): 2054 points, 65 transfers, 112 hit points
- 3GW decay (1.00,0.85,0.70): 2093 points, 59 transfers, 92 hit points
- 6GW decay (1.00,0.85,0.70,0.55,0.40,0.25): 2042 points, 65 transfers, 116 hit points

No-transfer control = 1425 points in all arms.

Selected strategy proxy: 3GW decay.
It beats 3GW equal by 39 points and 6GW decay by 51 points, while also using
fewer transfers and fewer hit points.

Interpretation:
- equal weighting over three GWs appears too aggressive;
- the six-GW horizon appears to overreact to longer-range forecast noise;
- short horizon + decay is the best of the tested policies.

Next: use 3GW decay as the primary transfer policy for the vFinal full-season replay,
while optionally retaining 6GW decay as a reporting comparator after vFinal rolling
origin-horizon forecasts are regenerated.
