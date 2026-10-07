# 2024/25 historical data checkpoint — data only

Status: **NOT_READY** for an independent, strictly cutoff-safe replay of the unchanged locked model. Collection/preparation/audits are complete for the sources successfully captured, not a claim of complete historical input coverage. No model fit, forecast, simulation, mathematics, cold-start, search or scoring changes were made. No existing 2025/26 files were modified.

Started from `2c118102c34469acdaaa89d25430f11439cb212b` on `audit-role-minutes-20261001`; each publication builds on the current branch HEAD. The user-supplied contract remains MM locked → PM/vFinal locked → TS v3 locked, horizon 6, rho 0.60, weights (1,.60,.36,.216,.1296,.07776), hit uncertainty buffer 1.0, chips OFF, GW1–5 cold start, GW6+ locked chain. 2,125 points is the supplied 2025/26 reference, not a newly reproduced result.

## Restore and reproduce this data audit

```bash
python scripts/restore_2024_25_data_checkpoint.py
python -m unittest discover -s tests -p test_2024_25_data_audit.py -v
python scripts/audit_2024_25_historical_layer.py
```

Pandas is required. No network is needed. Repository checkpoint parts preserve the raw source bytes, Core identity exports, all derived inputs and audit reports. Each part and the joined archive have SHA-256 checksums. The restorer refuses any differing existing file, traversal, other-season path or symlink. `source_manifest.json` records source URLs, external pinned commits, Git blob checksums where present, SHA-256 and retrieval time. `prepared_manifest.json` lists derived-file hashes. Collection workflow artifacts/caches are supplementary, not the only copy of the data.

The online collector is `scripts/collect_2024_25_historical_layer.py`, configured by `research/season_2024_25_v1/config.json`. It caches immutable HTTP captures and refuses differing raw bytes. A new capture of mutable provider responses belongs in a new versioned checkpoint, not this v1. The offline auditor never imports or invokes the model.

## Sources and actual coverage

Read the checked-in `collection_summary.json`, `coverage_by_competition.json`, `coverage_by_gw.csv`, `coverage_by_gw_component.csv`, `coverage_by_component.csv`, `provider_stat_field_coverage.json`, and `identity_audit.json` for exact counts. The latter files distinguish row coverage from usable predeadline coverage.

| Competition | Captured PL-club matches |
|---|---:|
| Premier League | 380 |
| Champions League | 46 |
| Europa League | 29 |
| Conference League | 13 |
| Conference qualification | 2 |
| FA Cup | 45 |
| EFL Cup | 42 |
| Total | **557** |

These are inventories from the validated provider, not an independent federation-level completeness certificate. There are 19,600 PL-club lineup/player rows: 19,540 mapped, 60 unresolved rows involving 35 provider identities, zero ambiguous rows and zero forced fuzzy matches. All 15,188 PL lineup/player rows are mapped. The mapped rating ledger has 13,614 original provider ratings and raw role inputs have 10,703 starter rows. Bench-only unused substitutes do not necessarily have minutes or ratings. Competitions outside the six requested families, including Community Shield, are not included in this inventory.

* Vaastav/Fantasy-Premier-League: pinned 2024/25 GW1–38 CSVs, fixture outcomes, FPL stats, teams, stable player codes, end-season identity reference and Understat files. All 380 PL fixtures; 27,283 actual player-fixture rows; 26,919 aggregated player-GW rows. All 784 FPL players map to existing internal UUIDs. Preserve the 322 Assistant Manager rows in raw/original actuals but exclude them from prepared player inputs: Assistant Manager is not a CAM role, and chips are OFF.
* Randdalf/fplcache: the official bootstrap API content archived in 38 nearest nominal predeadline payloads. 27,159 candidate player/GW records with prices, team/position, status/news/news_added and both chance fields. Official event deadline values are retained. None of the 38 capture clocks could be certified by surviving GitHub server job metadata. Candidate rows are quarantined; strict forecast eligibility is false and normalized availability remains UNKNOWN. This is stronger coverage of candidate bytes than zero snapshots, but **zero certified exact predeadline snapshots**.
* olbauday/FPL-Core-Insights: pinned 2024/25 PL match/team/player-event CSVs, including xG/xA, shots/SOT, defensive and keeper events. Existing frozen Historical Core 2024/25 rows and UUIDs are retained. Core `observed_at` is a 2026 ingestion timestamp, not historical publication.
* FotMob: independently validated competition identities for PL (47), CL (42), EL (73), Conference (10216), Conference qualification (10615), FA Cup (132), EFL Cup (133). Final league inventories and full match payloads provide kickoff, stage/round, opponents, results, starters/subs, minutes, raw stats, original 0–10 ratings and formation layouts. The initial 525 probe was AFC Champions League Elite and is quarantined, never counted as Conference data. Provider names are validated, not inferred from a numeric ID alone. Both Chelsea qualification matches are collected separately.
* Football-data.co.uk: captured 2024/25 E0 CSV, 380 results with shots and SOT. Raw local-time fields require UK timezone handling; join by exact teams/date to official UTC fixture identity before using kickoff.
* ESPN: six inventory requests returned HTTP 400. Failures are recorded; no ESPN coverage is claimed.

Captured Understat folders include legacy team files. They are raw evidence, not validated 2024/25 replay inputs: filter season/date/team and deduplicate before any later use. Provider stats preserve their own keys/scales; FPL expected assists and provider xA are not silently substituted. Rich event nulls are not filled with zero.

## Files the eventual integration should read

All prepared inputs are under `data_v1_1/derived/season_2024_25_v1/`:

| File | Intended use / restriction |
|---|---|
| `deadlines.json` | 38 official event deadline values reconstructed from archived payload |
| `eligible_player_fixture_actuals.csv.gz` | Exact FPL outcomes, per fixture; never same-GW features |
| `player_gw_actuals.csv.gz` | Aggregated outcome targets including DGW sums |
| `pl_fixture_actuals.csv` | Final PL results/fixture identities; not a historical future schedule |
| `player_identity.csv`, `provider_identity_mapping.json` | Existing UUID mapping; end-season team column is identity reference only |
| `reference_player_identity_rows.jsonl.gz`, `reference_player_names.jsonl.gz` | Exact known FPL/Opta anchors, not forecast history |
| `all_competition_match_actuals.jsonl.gz` | Stable internal match IDs, provider IDs, competitions, stages, kickoffs; future_schedule_forecast_eligible=false |
| `all_competition_player_observations.jsonl.gz` | Minutes, starts, keeper/attack/defensive raw stats; unmapped cases retained |
| `raw_role_inputs.jsonl.gz` | Formation, provider array slot, position ID and planned layout; no classified q/H |
| `player_match_ratings.csv.gz` | Unnormalized ratings with explicit timing proxy; strict_forecast_eligible=false |
| `deadline_player_candidates.jsonl.gz`, `availability_candidates.jsonl.gz` | Conditional snapshot research only; quarantined if timing_verified=false |
| `unresolved_provider_identities.jsonl.gz` | Unresolved/ambiguous cases; no forced fuzzy mapping |
| `existing_core_*.jsonl.gz`, `core_schema.json` | Frozen season export with original provenance and schema |

PL provider fixtures are mapped by exact home/away/UTC kickoff to existing FPL fixture UUIDs. Non-PL matches use a deterministic namespaced UUID anchored to the season and provider match ID because no existing 2024/25 cup identity was present. Providers map first through exact known Opta IDs; otherwise exact normalized name + historical team + same PL fixture membership. Validated stable provider IDs propagate identity to cups. Conflicting IDs remain ambiguous. Name normalization removes accents/punctuation; it never performs fuzzy matching or surname-only guessing. Identity propagation is not propagation of later ratings, club membership, availability or performance.

## Cutoff and quality contract

`EXACT_POSTMATCH` describes an outcome value, not its historical publication vintage. `RECONSTRUCTED_CUTOFF_SAFE` is used for static identity and archived official event deadline values. `PROXY_CUTOFF_SAFE` labels only the explicit historical availability assumption: provider kickoff + **4 hours**, allowing regulation/extra time; existing Core +3h fields remain separate. Publication/revision timestamps are unknown. Strict forecast eligibility is false; a later user-approved conditional replay must explicitly opt in to proxies and report the limitation. Never relabel a 2026 retrieval as predeadline observation.

`EXACT_PREDEADLINE` requires verified historical capture strictly before cutoff; there are currently no certified candidate rows. Missing strict input is `UNAVAILABLE`. A filename/Git author clock or `news_added` alone does not certify validity of an entire archived snapshot. Do not infer AVAILABLE from missing news. The strict carry-forward count is zero because no certified initial state exists; conditional candidates retain raw fields for further provenance research.

The offline history selector enforces `available_at_proxy < cutoff`, excludes missing identities and never includes target/future events. Per-GW coverage counts are historical event rows available **under the proxy**, not strict actual vintage coverage. BGW/DGW labels in coverage are final outcomes, not evidence those assignments were known before each deadline. Final cup qualification, draw, opponent or rescheduling information is forecast-ineligible until separately sourced historical publication evidence exists.

Formation layouts are planned lineup geometry, **not measured average positions**. All measured-average-position fields are explicitly null/UNAVAILABLE. The existing classifier, q/H and its priority rules have not been changed or partially replaced. Formation changes and prior-season role bootstrap also remain incomplete. Rating/stat revision vintage is unavailable even when the postmatch value is exact.

## Replay blockers and existing workflow

The precise blockers are machine-readable in `readiness.json` and `leakage_audit.json`:

1. All 38 bootstrap candidates lack independent capture-time verification: strict price/cohort/status snapshots cannot yet be certified.
2. Historical future fixture versions and cup draw/qualification knowledge are not reconstructed.
3. Measured average positions and prior-season role bootstrap are incomplete; exact existing q/H pipeline parity is not established.
4. Current locked runners bind SQL seasons, raw/derived paths and cold-start artifacts to 2025/26. Changing data folder names alone would silently use the wrong season.
5. `scripts/reproduce_pstart_v2_fixture_minutes.py` explicitly fits on **2023/24 + 2024/25** and holds out 2025/26. Thus at least this baseline already used the requested test season. This does not establish the training provenance of every locked final component; review those separately. Do not retrain as an unreported repair.
6. FPL defensive contribution points were introduced in 2025/26, so an unchanged PM score target differs from official 2024/25 scoring. Preserve official actuals; do not invent defensive contribution FPL points for 2024/25. Official source: https://www.premierleague.com/en/news/4361991.
7. Historical publication/revision timestamps for event stats/ratings remain proxies, not certified vintages.

The existing chain to preserve is `.github/workflows/final-locked-chain-gw1-38.yml`, with `reproduce_pstart_v2_fixture_minutes.py` → `build_reproducible_role_benchmark.py` → `build_workload_features.py` → `run_fa_match_importance_rebuild.py` → `run_locked_mm_gw6_38.py` → `run_rolling_vfinal_gw6_38.py` → `run_ts_v3_final_chain_gw6.py`. Evidence with original blob hashes and relevant source lines is in `locked_pipeline_provenance.json`. **Do not run this workflow as a 2024/25 replay yet**: it presently targets 2025/26 and includes feature fits. There is no truthful unchanged 2024/25 replay command at this checkpoint. A future data/path/season adapter must preserve the frozen mathematics/parameters, address training provenance and scoring interpretation, and prove cutoff behavior before a replay can be called fair. No such model/replay work is included here.
