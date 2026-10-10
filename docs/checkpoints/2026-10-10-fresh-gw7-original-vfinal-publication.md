# Fresh GW7–12 original MM → vFinal publication

Continues latest `free-github-static-20261010` HEAD. Model mathematics, fitted historical priors, duration constants, TS search configuration, rho/weights/hit buffer and chip thresholds remain unchanged. No mathematical `src/` file was edited.

## Completed, measured results

Official current-season sources were refreshed in workflow [38060470515](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38060470515). The common cutoff follows all source captures: **2026-10-10T14:39:56.350918+00:00**; official next deadline is **2026-10-17T10:00:00+00:00**, GW7. The source checkpoint contains 119 checksum-verified files; 667 exact stable identities, 4,002 target rows, 83 completed provider matches, 2,011 original-scale ratings and 667 current-GW Team News records. No unresolved current identities. There are 242 players without confirmed starting-role history. FA Cup's wrong-season provider response is explicitly rejected.

Original simulation workflow [38060960735](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38060960735) **passed**. It rebuilt numerical adapters and simulator outputs twice at the fresh cutoff, with exact equality in all 3,165 training rows, 4,002 MM rows, 60 team-goal forecasts, 4,002 complete simulator-input rows and 4,002 xP rows. Same numerical parameters, same input cutoff and seeds; no tuning.

One actual GW7 fixture has 59 mapped player rows, one GW has 667, and GW7–12 has 60 fixtures / 4,002 rows. One-match and one-GW outputs equal their six-GW subsets exactly. **179** current-GW exclusions have zero simulated minutes and points. Expected starters sum to eleven on every team side, maximum error **1.5116796703296131e-12**. Target outcome fields are absent and all five audited evidence timestamps have **0** post-cutoff rows.

| Player | GW7 original vFinal xP | Analytic locked MM xMins |
|---|---:|---:|
| Haaland | 6.3825 | 77.3865124833 |
| B. Fernandes | 5.0950 | 85.0389263103 |
| Saka | 5.0525 | 76.3333066677 |
| Mbeumo | 4.6350 | 84.9545692108 |

These are actual frozen-simulator outputs, not FPL `ep_next` or experimental xP. They remain **diagnostic** because source completeness and the four-chip release contract are not satisfied.

## Reproduction fix and scope

The old drift arose first in original `np.polyfit` sequence slopes at ~1e-14, which changed the unchanged standardized logistic L-BFGS conditional-sub fit. A one-feature causal audit restores every coefficient/probability exactly. The original team-latent numerical fit also differed across numerical runtimes despite equal observations. Hash/thread/NumPy/OpenBLAS CPU-dispatch controls now apply before imports, without modifying original formulas/tolerances/seeds.

The fixed runtime passed two complete numerical rebuilds for both frozen GW6 and fresh GW7. Locally regenerated GW6 MM and team-lambda DataFrames also match GitHub exactly. The exact comparison covers the numerical source adapters; historical roster/role input completeness remains a separate source-quality question. This is not a promise of bitwise equality on arbitrary unpinned machines. Immutable original GW6 sources/outputs remain retained as secondary checkpoints.

## Permanent artifacts and publication

- `model/checkpoints/live_gw7_sources_20261010_v1/`: 119 raw/source files, checksums and source metadata, append-only alongside older versions.
- `model/checkpoints/live_vfinal_gw7_20261010_v1/`: 49 input/output/audit files, including simulator inputs, complete predictions, MM rows, training rows, penalty/BPS ledgers, metadata and exact rebuild receipt.
- `analysis/results/live-gw7-original-vfinal-20261010-v1/`: directly readable reproduction, leakage/scope, BPS and training audits.
- `scripts/restore_live_vfinal_checkpoint.py --checkpoint model/checkpoints/live_vfinal_gw7_20261010_v1`: verifies all part/archive/file checksums before restoring.

Pages publishes the fresh output through the original desktop builder. A separate publication receipt verifies the exact input/output hashes and cutoff before changing displayed provenance. Completed numerical reproduction removes the obsolete instability warning; it does not promote release certification.

## TS and chips

`manager-state.html` implements import/export of actual squad, bank, FT, purchase prices, observation time and chip histories. Prices are mandatory and never guessed from current prices. Duplicate same-half chip usage is rejected. The plan receipt includes a manager-state SHA-256, so the desktop refuses another squad's plan even when its forecast cutoff matches.

`live-manager-plan.yml` uses the fresh actual vFinal xP and original TS v3 configuration, original XI/captain optimization and first-action semantics. FH/WC/BB use the original locked historical SIMPLE_FH_WC branch and coordinator. A legal synthetic **regression fixture**, explicitly not the user's manager state, passes the complete six-GW planner and partial chip assessment without mutating input state. Actual personalized recommendations are unavailable until actual manager-state is supplied. No official FPL transfers are performed.

TC was investigated: `run_tc_long_horizon_origin.py` is hardcoded to 2025/26 observations and explicitly marks its future calendar `REALIZED_GW_CALENDAR_PROXY_NOT_CUTOFF_SAFE`. Reusing those archived TC opportunities for 2026/27 would be invalid. A complete cutoff-safe current-half TC scenario ledger and the original manual decision gate are still required. Six-GW mean forecasts are not substituted for it. Full four-chip choice and future chip timing therefore remain **Not Available**.

## Precise remaining blockers

1. BPS: 1,204 verified rows; 334 quarantined. Missing overlapping fields are chances_created 96, dispossessed 100, was_fouled 244, accurate_passes_percent 16, tackles_won 1. Every incomplete row/field is logged. The raw team-stat inventory lacks an additive chances-created total; shotmaps do not contain assist-player identities; successful-tackle semantics cannot be inferred from total tackles. No unverifiable zeros or FPL-total-BPS residual replacements are introduced.
2. MM training: predeadline roster snapshots exist for GW1–5, but only 3,165 observation-matched rows are used; 37 wrong-registration/club rows are rejected. Every unused registered player's historical observations and full provider semantics are still not recovered. Snapshots 76–387 minutes before deadlines can miss late news.
3. Provider outcomes use a documented kickoff+4h publication proxy, not an exact publication timestamp. Retrospectively fetched provider-stat revisions cannot certify exact historical feature availability. At this cutoff, usable observed histories are GW1–5; no unobserved GW6 statistics are invented.
4. Current-half TC scenarios/manual eligibility and a complete four-chip prospective plan are unavailable; actual user manager-state is not present in this session.

`locked_model_active=false`. The app and all source/prediction artifacts are concrete, reproducible diagnostic progress, not a claim that the entire live chain is certified.

Official scoring rules were checked against the existing 2026/27 BPS implementation: [PL BPS changes](https://www.premierleague.com/en/news/4679946/whats-new-in-202627-fantasy-changes-to-bonus-points-system) and [PL season rules/chips](https://www.premierleague.com/en/news/4679873/all-you-need-to-know-about-changes-to-fpl-for-202627). Existing scoring code already selects `bps_rules='2026-27'`; no scoring constants were changed.
