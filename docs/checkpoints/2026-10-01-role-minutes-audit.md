# Role/minutes checkpoint audit — 2026-10-01

Status: repository audit completed; requested model work blocked by missing checkpoint inputs.

## Source of truth and inspected scope

- Repository: https://github.com/pdamkier-del/fpl-analytics-app
- Main HEAD: `1ca802dd7cf2112b07f0649872535b0a9b49999a` (Publish FPL Analytics v2.2, 2026-09-23).
- Other remote branch: `ui-team-transfer`, HEAD `7bf1aeefa51b96f9cfed7cead6bbe282a9f11804`.
- Inspected all 11 commits reachable from both branches and all historical tracked paths (73 unique blobs).
- Inspected all five tracked update ZIP archives, including their model files. No Git tags or GitHub releases were found.
- Read README.md, .gitignore, model/engine.py, defaults, active configuration and official version metadata.

## Findings

`model/engine.py` passes through the Live Data Bridge. Its comments explicitly say forecast mathematics remains in that bridge; changing configuration does not calculate new forecasts. The official `v0.1-baseline` configuration is an app bridge configuration, not the historical v1.0 or P(start) v2 benchmark requested in the handoff.

No implementation of fine-role import, CAM classification, recency-weighted q/H, role-constrained P(start), full minute decomposition, Historical Core, registration/cutoff audits, historical model replay or the reported role-aware benchmark was found in this history. No test suite is tracked. Model runs are explicitly ignored (`model/runs/`), so untracked local experiments could exist elsewhere; this audit cannot inspect them.

Current model/base_data.json contains:

| Item | Coverage |
| --- | --- |
| Season | 2026/27 |
| Clubs | 20 |
| Fixtures | 380 (current-season schedule, not 2025/26 historical role coverage) |
| Forecast player records | 562 |
| Actual records | 3,250 |
| Actual GWs | 1–5 |
| Source model | live_simple_baseline_v0.1 |
| Source update | 2026-09-22 20:12 |

The ZIP and gzip data snapshots use this same season/model metadata. Actual records include broad FPL `pos`, minutes and starts, but no formation, lineup slot, average position, fine role or stable player_uuid field. Role coverage and CAM metrics are therefore unavailable, rather than verified zero coverage of a supplied historical dataset.

## Benchmark status

The handoff reports baseline Brier ~0.07715, log-loss ~0.2577, xMins MAE ~11.96 and role-aware ~0.07646/~0.2509/~11.64. None is verified against an experiment artifact here. A text match for `0.07646` is a player forecast `preturn=0.07646481651`, not a Brier benchmark.

GW22–38 contains 17 GW numbers, whereas the handoff also cites 27/27 tested GWs. Recover the actual evaluation definition before treating either as validated scope.

No new model was created, trained, promoted or integrated. No OOS metrics, team/GW stability, role slices, CAM results or replay differences can be computed honestly from this checkout.

## Checks performed

- Python AST syntax check: all 4 tracked Python files pass.
- JSON parse check: defaults, active config, official baseline config and base_data pass.
- Read-only config/version smoke checks pass: active mode is bridge_passthrough and the version list loads.
- No existing test suite found; these checks are not model validation.
- Existing engine, forecasts, data and benchmark configuration remain unchanged.

## Resume requirements

Recover the existing role/minutes checkpoint source code, Historical Core/caches, cutoff metadata, tests and benchmark artifacts from its original location or checkpoint package. Import the recovered existing checkpoint on a separate branch with provenance; do not rebuild it from current app forecasts or substitute an external data-source repo for this repository.

Then reproduce its tests and benchmark, audit role coverage, isolate explicit CAM corrections, run chronological OOS comparisons and only then proceed to minute decomposition and identical-rule FPL replay.

## Remote persistence blocker

GitHub repository metadata reports `push: true`, but creating `audit-role-minutes-20261001` through the connected GitHub integration returned HTTP 403, `Resource not accessible by integration`. The audit is committed locally; remote persistence requires enabling write access for this integration. Main was not modified.
