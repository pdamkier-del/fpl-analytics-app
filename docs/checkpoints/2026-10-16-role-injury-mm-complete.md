# Completed MM-only role/injury research — 2026-10-16

Branch: `research-role-injury-club-audit-20261016`, PR #8. Production sources unchanged. `locked_model_active=false`. No PM, points, TS or chip execution.

Read [the results](../research/2026-10-16-role-injury-mm-results.md) before continuing. Historical replay is complete; do not restart source collection or claim this is just a framework.

- 13 controlled arms; evaluation 2024/25 GW22–38 (13,105 rows /171 fixtures), 2025/26 GW6–38 (26,159 rows /330 fixtures).
- Strict FPL-news matching across GW6–38: 23,974/24,072 and 26,074/26,159 rows. 349/357 observed source-medical episodes; 282/294 selection-status returns; zero verified training-return statements. These are not clinical clearance labels.
- Original MAE 12.653/10.533; frozen role MM 12.309/10.387; role+hard-news+projection 11.272/10.387; role+source-chance 11.160/10.212; exploratory chance+preserved starter duration 11.156/10.203.
- Full pre-injury tuple carry worsens return MAE. Duration-only carry is promising, especially in 2025/26; no production promotion.
- 28 focused regressions pass. CI runs 38924972037 and 38925148538 both pass. All ten result members reproduce byte-for-byte locally against the permanent CI capsule.

Restore using `scripts/archive_role_injury_mm.py --restore DESTINATION`; archive and member hashes are checked. Sources, MM reference, detailed predictions and profiles are in `checkpoints/role_injury_mm_20261016/`. Readable per-club results, coverage and reproduction manifest are in `analysis/results/role-injury-mm-20261016/`. Frozen MM reference is PR #4 commit `6d875a65251fb62f691dc0386ea81aeb29d27c0f`. Workflows use permanent source evidence rather than expiring artifacts.

Next gate: new prospective/unused MM evaluation; independently calibrated FPL availability interpretation; verified medical/training returns and historical outcome-publication clocks. Do not run PM/TS for this MM-only task. Do not replace baseline or claim full live certification.

## Follow-up probability and temporal robustness

Completed read-only audit in `scripts/validate_mm_probability_robustness.py`; report `docs/research/2026-10-16-mm-probability-robustness.md`; full gzip JSON + reliability/endpoint CSVs in `analysis/results/mm-probability-robustness-20261016/`. 38 focused tests pass locally. Seven existing arms audited; no new model fitting, simulations or prediction edits.

4-GW block MAE delta, source chance versus primary: -0.1118 [-0.1367,-0.0872] / -0.1752 [-0.4256,-0.0358]. The 2025 gain is weaker late in the season. 35 exact-zero appearance forecasts conflict with actual play; three suspension cases reveal GW-wide gating into the second DGW fixture (Jones GW25, Nketiah/Guéhi GW32). Raw suspension day/month matches that later match, but no complete verified expiry timestamp has been invented or injected. Fixture-scoped authoritative suspension data remain a priority.

Initial follow-up CI missed the requests dependency (fixed); compressed gzip bytes differed between environments, so exact reproduction compares decompressed JSON bytes and CSV bytes while retaining frozen-input/production hash checks. Final dedicated workflow run 38927430361 passed all 38 tests, exact JSON/CSV reproduction, frozen prediction SHA and unchanged production checks. Production is unchanged.

## Superseding all-club evaluation

The full requested club audit is complete: read [2026-10-16-mm-all-clubs-complete.md](2026-10-16-mm-all-clubs-complete.md). It includes all40evaluation club-seasons, 9MM arms, 540 club/model/phase records, 5,400 per-model largest-error rows, return matches1–3, temporal intervals and isolated duration ablations. Do not restart the earlier source/framework work.
