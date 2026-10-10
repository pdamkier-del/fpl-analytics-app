# Current-season integration checkpoint — 2026-10-10

**NOT_READY_FOR_LOCKED_LIVE_RELEASE.** The website and a current source-input checkpoint are published. The complete locked MM → PM/vFinal → TS v3 → four-chip chain has NOT run on current 2026/27 data. Neither a one-GW nor a six-GW model integration test is complete. Do not treat the six-GW source matrix or passing unit tests as model execution.

Continuation destination is `free-github-static-20261010`, the currently deployed descendant containing the locked 2026-10-09 model and newer UI. Work started above its then-current HEAD, preserving subsequent UI commits through Git Data API updates with expected-HEAD checks. No model source, coefficients, hyperparameters, chip policies or TS search code was modified.

## What was established

Successful collection and data audit: [Actions run 38034876900](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38034876900), source commit `662582280d52e9dee1c6e610a9bb38770724d144`.

- Official next event: GW6, deadline 2026-10-10 10:00 UTC.
- Official roster: 667 players and 380 fixtures.
- 664 UUIDs reused from Historical Core through exact stable FPL codes; three newly registered official codes receive deterministic namespaced UUIDs in a separate prospective identity ledger. No ambiguous existing mapping is overwritten.
- All 50 completed PL games matched by exact club identity, home/away and UTC kickoff. Leeds United → Leeds is an explicit club alias.
- 83 completed official club games: PL 50, Champions League 5, Europa League 3, Conference qualification 2, EFL Cup 23.
- 2,011 original-scale FotMob ratings; zero duplicated provider/player/match rows, zero ratings outside 0–10.
- Official predeadline Team News for all 667 current players, captured before the current deadline. Chance is scoped to origin GW6, not treated as an observed future-GW chance.
- 1,518 classified starter rows using unchanged formation-first classifier and RoleHistory. Importance scales remain q=0.1/H=0.4, floor=0.35; role half-lives remain 3/10.
- A 4,002-row origin-state source matrix covering GW6–11 (667 players per GW). Uses unchanged role/history, rating and workload modules. This is NOT the full MM inference feature matrix.
- 3,202 exact official FPL player-fixture event rows from completed GW1–5, with xG/xA, defensive contribution, goals, FPL assists, minutes/starts, cards, own goals, saves, penalties, BPS and actual points. Fourteen records with unresolved historical membership remain quarantined.
- 61 selected existing/new regression tests passed; frontend changes syntax-checked. These are unit/regression and source-data checks, not an end-to-end live-model test.

## Frozen MM contract incompatibility

`run_mm_v2_team_news_availability_experiment.policy_caps` assigns cap=0 to OUT/SUSPENDED. The locked runner projects **P(start)** to this cap. It passes the untouched substitute branch to `run_mm_unified_official_roles.compose`:

`xMins = P(start) * start_minutes + (1 - P(start)) * q_sub * sub_minutes`.

A reproducible counterexample with P(start)=0, q_sub=0.20 and sub_minutes=20 yields **4 xMins**, while `mm_release.validate_mm_release` explicitly rejects a hard-unavailable player with positive xMins. The existing code does not gate the substitute branch in that runner. `tests/test_live_locked_inputs.py` proves both the existing formula output and the release rejection. This counterexample is NOT an executed current-player forecast or an estimated incidence count.

No probability/minutes correction was silently added. The instruction to keep model mathematics unchanged prevents certifying a corrected release without resolving the intended frozen availability contract.

## Data quality and remaining work

| Component | State and limitations |
|---|---|
| Identities | Current FPL roster 667/667 mapped; 35 non-current-FPL provider rows unresolved and logged. Former-club appearances use exact Opta/FPL code, not a forced current-team join. |
| Roles | Formation/confirmed-slot evidence available; average-position evidence unavailable. 242 current players have no observed current-season starter role and remain UNKNOWN. Two academy-heavy EFL sides fail the complete mapped-XI gate; no fabricated roles. |
| Availability | Exact current observed snapshot for origin GW6; no current dataset proving historical predeadline GW1–5 bootstrap/news/position snapshots. Historical current-team membership is a declared reconstruction, not an exact predeadline roster. |
| Events/ratings | Match-history availability is explicitly `kickoff + 4h`, classified PROXY_CUTOFF_SAFE; actual publication time is unavailable. Real capture timestamps and raw payloads are preserved separately. This proxy is not proof of provider publication at that time. |
| FA Cup | Provider ignored the requested 2026/27 season and returned 2025/26; quarantined. No prior-season fixtures are relabelled as current-season games. |
| MM | Source q/H/workload/ratings/news matrix prepared. Frozen base-logit, duration, sequence and performance builders still require a complete current-season training/inference adapter and membership/snapshot validation. Availability contract conflict unresolved. |
| PM/vFinal | Official event inputs staged. Full current team-latent/keeper-SOT, penalties, BPS action-history and fixture-simulation adapter remains incomplete. No phase5q or ep_next substitute. |
| TS v3/chips | Frozen implementations/configurations retained. No current verified PM outputs, user-state-linked TS calculation or TC sample ledger; hence no certified current recommendations. |
| App | Primary Forecast uses final-release-only view, with explicit blocked state. Historical and separately labelled experimental pages are not a certified finalmodel. Deployment success does not certify forecasts. |

Current origin source matrix deliberately carries frozen **origin** state across the six target GWs, as the existing rolling PM runner does. It does not claim to know later team news, future lineups or match outcomes. Historical field proxies and unknowns remain visible.

## Permanent repository checkpoint

`model/checkpoints/live_inputs_20261010_v1/PARTS_MANIFEST.json` lists 131 source/derived files with SHA-256 checksums, plus 39 lossless archive parts (~5 MB total). Includes raw HTTP captures, source manifests, identity/coverage audits, original-scale ratings, news, classified starters, source feature matrix and official player-event records. This checkpoint is in git; it does not depend on an expiring Actions artifact or a local ZIP.

Restore to an empty destination:

```sh
python scripts/restore_live_input_checkpoint.py --out work/restored-live-inputs
```

The restorer verifies every part, archive membership and each extracted file, and refuses to overwrite differing files. Existing 2025/26 data is unaffected.

Reproduce fresh source collection/audit in the existing repo with Python 3.12:

```sh
pip install -r requirements-model-checkpoint.txt -r requirements-model-tests.txt requests
python scripts/restore_core_checkpoint.py --out work/core.sqlite3
python scripts/collect_current_locked_inputs.py
python scripts/audit_current_locked_inputs.py
PYTHONPATH=src:scripts pytest -q tests/test_live_locked_inputs.py tests/test_mm_release.py
```

Do not promote the staged source matrix to `work/live-final-model/manifest.json`: it is missing verified MM/PM/TS/chip execution artifacts. `publish_final_model.py` must continue to report a blocked final release.
