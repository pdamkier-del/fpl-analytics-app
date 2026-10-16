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
