# GW7–12 v2: resumed publication after interruption

Continues branch HEAD `b3a2a802c42bd930cc6d88486ad61d98cf154eb3`. The corrected original MM → vFinal run [38062591951](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38062591951) passed before the interruption. This checkpoint finishes preserving and publishing that run. No mathematical model source, coefficient, parameter, search setting, seed, or chip decision policy is changed.

## Corrected data and actual predictions

Fourteen official zero-minute/zero-start observations are recovered using their archived predeadline club, rather than the player's present club. Training grows from 3,165 to **3,179** verified partial-cohort rows. The recovery ledger retains player UUID, FPL ID, historical fixture/GW, source and both club IDs. Unsupported cases are still rejected.

Cutoff remains **2026-10-10T14:39:56.350918+00:00**, forecast GW7–12. Two complete numerical rebuilds are exactly equal across training features, 4,002 MM rows, 60 team forecasts, 4,002 simulator inputs and 4,002 xP rows. The 59-row one-match and 667-row one-GW outputs equal their six-GW subsets. All 179 documented unavailable rows have zero simulated minutes/points; the expected starter sum error is at most 2.409e-12. Five audited evidence timestamps have zero post-cutoff rows, and target outcome columns are empty.

| Player | GW7 original vFinal xP | MM analytic xMins |
|---|---:|---:|
| Haaland | 6.2200 | 75.8464 |
| Mbeumo | 5.1325 | 84.0845 |
| B. Fernandes | 4.9100 | 84.1394 |
| Saka | 4.6475 | 75.7953 |

These supersede the v1 forecast values at the same cutoff because historical input coverage improved. They remain diagnostic.

## Persistence and delivery

`model/checkpoints/live_vfinal_gw7_20261010_v2/` preserves 57 source-adapter/input/output/audit files, including the 14-row recovery ledger and the corrected source features. All parts, the archive and each restored file are SHA-256 verified. Archive SHA-256: `85a7b60d34c9da0529c491b5ecd615c6ecf75d409b2061749ea5d62155555452`. Previous GW6 and GW7 v1 checkpoints remain unchanged.

Pages and the manager-plan workflow now restore v2. Publication verifies the exact simulator input/output checksums against the receipt before showing the new provenance. Readable evidence is in `analysis/results/live-gw7-original-vfinal-20261010-v2/`.

The replay workflow now verifies both GW6 v1 and GW7 v2 under the fixed numerical launcher. Local validation: **58 regression tests passed**, manager JavaScript syntax passed, and v2 checkpoint restoration passed. The new regression forces a chip adapter failure and verifies that the original completed six-GW TS plan and XI/captain remain available while chip output becomes Not Available.

## Transfers and chips

The existing manager-state screen accepts actual squad, bank, FT, mandatory purchase prices, observation time and all four chip histories. Original TS v3 and FH/WC/BB calls are retained. The integration wrapper now records a failed chip assessment without discarding a successful TS calculation; it never substitutes another chip algorithm. Input state is not mutated and no official FPL action is performed.

No actual user manager-state is supplied, so no personalized transfer recommendation or chip timing is claimed. A legal regression fixture tests original planner behavior; it is not the user's team. TC and full future chip timing still require the original cutoff-safe current-half scenarios and manual decision requirements.

## Remaining blockers

1. BPS: 1,204 verified historical rows; 334 incomplete rows quarantined. Missing overlapping features: chances_created 96, dispossessed 100, was_fouled 244, accurate_passes_percent 16, tackles_won 1. No missing observation is invented.
2. MM: the corrected 3,179-row historical cohort remains partial; unused registered players and some provider semantics are not fully verified. Historical snapshots precede deadlines by 76–387 minutes and may miss late news.
3. Historical provider availability still uses a documented kickoff+4h proxy and retrospective revisions, not complete exact historical publication timestamps.
4. Actual squad/bank/FT/purchase-price/chip state and complete cutoff-safe TC scenarios remain absent. Full four-chip prospective planning is Not Available.

`locked_model_active=false`. Numerical reproducibility is verified in the controlled runtime; full source quality and live-chain certification are not. The desktop homepage remains published; [diagnostic forecast](https://pdamkier-del.github.io/fpl-analytics-app/vfinal-diagnostic.html) and [manager state](https://pdamkier-del.github.io/fpl-analytics-app/manager-state.html) use the original integration.
