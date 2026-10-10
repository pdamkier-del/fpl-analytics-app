# Original vFinal real-output checkpoint — 2026-10-10

**Status: partial diagnostic integration; NOT fully live-certified.**
`locked_model_active=false`. No locked MM/PM/TS/chip mathematical source, coefficients, search parameters or stopping thresholds were edited in this work. Existing desktop remains deployed independently of model certification.

## Starting point and successful original pipeline

Started from newest `free-github-static-20261010` HEAD `5acb7e8631a6fbfb1c141e912f13d115d354599b`, then published source integration commit `8829613f65eee85180354f366267d78c676fb1b7`.

- Original source→MM→complete vFinal workflow succeeded: <https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38056989718>.
- Original simulator, **400 draws per fixture**, frozen seed sequence `93000000 + fixture index`.
- Forecast origin GW6; fixed source cutoff **2026-10-10T07:35:11.016234+00:00**. This is not a claim that these files are a refreshed forecast for a later deadline.
- One chronological upcoming match at this cutoff: `live-2026-27-fpl-51`, kickoff `2026-10-10T11:30:00Z`, **60 rows**. Previous lexical selection picked GW10; only the test selector has been corrected.
- One GW: **10 fixtures, 667 player-fixture rows**.
- Six-GW forecast: **60 fixtures, 4,002 player-fixture rows, 667 stable players, GW6–11**.
- Scope-independent fixture seeds: one-match and one-GW xP exactly equal their corresponding rows in the six-GW simulation.
- All original point components reconcile to xP. Penalty-miss points are a subset of negative-event points and must not be added twice.
- **181 hard-unavailable GW6 rows** have zero simulated minutes and zero xP. Future GW news remains neutral; current exclusions are not propagated indefinitely.
- Expected starter mass: maximum deviation from eleven = **1.659117287999834e-12**.
- Target actual-start/minute columns are entirely empty. Historical input, source evidence, roster observation and Team News effective timestamps have **zero post-cutoff rows**.

These checks establish a reproducible diagnostic run, not a complete data-quality certificate.

## Penalty identity and BPS bridge

- 15 explicit regular penalty events in the archived shot events; shootouts excluded.
- **13 attempts mapped to current PL-player identities across all competitions**; **9 PL attempts**, with **100 verified PL team sides / 50 fixtures** including verified zero-penalty sides.
- Two foreign cup opponents remain explicitly outside the FPL identity namespace: Isaac Price (West Brom) and Nicolò Tresoldi (Club Brugge). They are not assigned invented FPL IDs. No unresolved PL penalty identities.
- Shot-event IDs, provider/team IDs, match IDs, outcomes, historical GWs, player UUIDs and source timestamps are retained in `verified_penalty_*.csv.gz`.
- **1,204 verified positive-minute BPS player-match rows**; **334 quarantined**. Missing fields overlap: chances_created 96, dispossessed 100, was_fouled 244, accurate_passes_percent 16, tackles_won 1.
- Raw-source zeros are accepted only if known player counts exhaust an observed complete team total. Missing totals do not imply zero. `tackles_won` is not silently replaced by total tackles.
- The canonical original `actual_background_ledger` builder is reused. Original development clipping bounds restored without current-season quantile fitting: **[-16.20711462450593, 36.0]**.
- External raw source is pinned to `olbauday/FPL-Core-Insights` commit `561bd00f699ec25ce095a0245e6ad52300ebdc01`, published before forecast cutoff. It is a data source, not our model repository. Raw GW1–5 fixtures/players/playermatchstats and checksums are committed append-only.

## Complete PM adapter

`build_live_vfinal_full_event_components.py` calls original `vfinal_replay_components.build_fixture_components` directly: dynamic role and position priors, soft performance goal/assist allocation, role-weighted DefCon and threshold calibration, discipline and own goals. Original keeper/penalty/BPS adapters compose the final simulator input. Previously computed goal_mu/assist_mu are preserved instead of replaced by preliminary simple-rate allocations.

GW6 examples from actual 400-draw original vFinal outputs:

| Player | Club | xP |
|---|---|---:|
| E. Le Fée | Sunderland | 7.0975 |
| Mbeumo | Manchester United | 6.6325 |
| Bruno Fernandes | Manchester United | 6.0975 |

These values are conditional on incomplete upstream coverage; they are not certified transfer recommendations. No tuning was applied to make them look plausible or improve historic results.

## TS/chip state and current blockers

`run_live_locked_ts.py` prepares the same forecast schema as the original rolling replay (including the original DGW nonappearance-product aggregation), and calls the existing TS planner using `run_joint_fh_wc_stopping_replay.cfg()` directly. It never substitutes generic planner defaults or historical proxy xP.

**No actual transfer/chip plan has been executed. Both are Not Available.** Real manager state is absent. The desktop's existing browser-local squad has player IDs/bench/captains, but not verified bank, FT, purchase prices or chip histories.

Required state JSON: `season`, `gw`, `source`, timezone-aware `observed_at <= forecast cutoff`, `bank_tenths`, `free_transfers` (1–5), `squad` (15 `{id,purchase_price_tenths}`), `chips_used` with all four chip names and earlier usage GWs. Missing purchase prices are rejected; current buying prices are not assumed to be historic purchase prices. TS cannot run until independent MM and PM source-quality gates are verified. Whole-chain activation is not used as an input prerequisite, avoiding a circular gate.

Remaining blockers:

1. **BPS completeness:** 334 player-match rows lack canonical verified actions; missing fields remain quarantined, and sparse priors make xP diagnostic. No credible field-level exact source has established all missing values.
2. **MM training quality:** 3,165 eligible archived GW1–5 rows; 37 postmatch rows rejected against predeadline rosters (34 unregistered, 3 wrong-club). Archived captures are 76–387 minutes before deadline and may miss late changes. The cohort does not yet include every archived registered unused player. Cup/Europe FotMob `tackles_won` semantics remain unverified. Existing frozen learning functions ran with an explicit history-only training mask; learned diagnostic outputs are not claimed to be a certified production estimator.
3. **Manager state:** genuine bank, FT, purchase prices and chip history are not available; no representative synthetic squad is reported as the user's team.
4. **Chip stopping inputs:** the locked TC future-option scenario coverage required by the original stopping policy is absent. No average-xP replication or historical future samples were inserted. Existing FH/WC/BB/TC strategy source is unchanged.
5. **Freshness:** these are frozen GW6 predeadline outputs. A later origin must collect its own sources, completed histories and archived deadline roster cohorts and rerun quality gates. Pages publication time does not refresh model input time.

## Permanent files, reproduction and tests

`model/checkpoints/live_vfinal_20261010_v1/manifest.json` identifies every immutable output and checksum; base64 parts preserve complete original simulator inputs, actual predictions, source bootstrap, verified penalty/BPS ledgers and audit reports in Git. This does not depend on expiring Actions artifacts.

```bash
python scripts/restore_live_vfinal_checkpoint.py
python scripts/audit_live_vfinal_outputs.py
python scripts/build_live_vfinal_desktop.py
python scripts/run_live_locked_ts.py
PYTHONPATH=src python -m pytest -q tests/test_live_vfinal_desktop.py tests/test_live_locked_ts_bridge.py tests/test_run_live_vfinal_joint_simulation.py tests/test_verified_live_penalty_bps.py tests/test_join_live_vfinal_inputs.py tests/test_assemble_live_vfinal_inputs.py tests/test_run_live_vfinal_bps.py tests/test_run_live_vfinal_penalty_state.py
```

29 targeted adapter/source/state/publication tests passed locally. The earlier complete Actions source/MM/PM pipeline passed all its regression stages. New publication checks also run in Pages and the complete readiness workflow.

Original simulation reproduction:

```bash
PYTHONPATH=src python scripts/run_live_vfinal_joint_simulation.py --scope one-match --input data_v1_1/derived/live_locked_inputs/2026-27-v1/vfinal_live_full_simulator_input.csv.gz --out data_v1_1/derived/live_locked_inputs/2026-27-v1/one_match_xp.csv.gz
PYTHONPATH=src python scripts/run_live_vfinal_joint_simulation.py --scope one-gw --input data_v1_1/derived/live_locked_inputs/2026-27-v1/vfinal_live_full_simulator_input.csv.gz --out data_v1_1/derived/live_locked_inputs/2026-27-v1/one_gw_xp.csv.gz
PYTHONPATH=src python scripts/run_live_vfinal_joint_simulation.py --input data_v1_1/derived/live_locked_inputs/2026-27-v1/vfinal_live_full_simulator_input.csv.gz
```

Published actual-output viewer: <https://pdamkier-del.github.io/fpl-analytics-app/vfinal-diagnostic.html>. The original main forecast remains release-gated and links to this clearly labelled diagnostic. It does not use FPL ep_next or the experimental model as vFinal.
