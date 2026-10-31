# Prior-only role-transition screen — 25 October 2026

Decision: reject this candidate; no active B or production change. This is a test of an additional signal, not proof of a general hierarchy defect or proof that every existing prediction is correct.

The existing B already uses last-start information, longer history and injury-return evidence. The tested addition distinguishes recent starts with an established soft-role rival available from starts during recorded unavailability, and adds current return pressure. Unknown status is not inferred injury/rest. The fixed protocol was written before scoring; no player-specific tuning or parameter search was performed.

## Historical screen

Both seasons use GW22–38, outfield players, earlier-known outcomes only. Lower is better. These are upstream MM results, before the original joint-role/normal-match PM layers.

| Season | Player-fixture rows | Start Brier before | After | Minute MAE before | After |
|---|---:|---:|---:|---:|---:|
| 2024/25 | 11,722 | 0.076465 | 0.076338 | 11.4365 | 11.4104 |
| 2025/26 | 12,377 | 0.072836 | 0.072946 | 10.8713 | 10.8805 |

Paired whole-fixture bootstrap 95% intervals for Brier change: 2024/25 [-0.0003074, +0.0000533]; 2025/26 [-0.0000842, +0.0003250]. Both include zero. The required improvement in each season fails. In the returning-rival cohort minute MAE also worsens (22.316→22.930 and 23.160→23.638); that descriptive result is not an extra retrospective acceptance gate.

`report.json` also contains recorded-availability cohorts, existing final joint-role diagnostics and descriptive forecasts by team-game age after a past-only role-change trigger. Those diagnostics do not establish a reproducible broad underprediction of new starters. They do not certify individual cases. Whole-team start bias is mechanically near zero because projection fixes ten outfield starts; cohort bias is more informative.

## Scope and limitations

- 66 chronological fitting origins. Frozen upstream predictions reproduce the archived joint-role experiment's input. Hard goalkeeper forecasts are unchanged; this candidate does not test a new goalkeeper hierarchy.
- Rivalry uses prior soft roles and co-selection, not a confirmed exclusive coach hierarchy. Full feature evidence and fit clocks are retained.
- Existing historical availability/role states and proxy outcome clocks are reused. Missing explicit news and tactical labels limit interpretation. These are reused research periods, not a fresh independent holdout.
- No candidate final-role/PM/xP/TS performance is claimed. Per protocol, the failed upstream screen ends this trial before a full PM replay. The existing normal-match constraints remain active: ten outfield plus one keeper, normalized 900+90 coverage, at most five substitutions and three live substitution windows in the modeled normal-match scope.
- No app deployment, active numerical source update, production change or external service deployment was made for this experiment.

## Reproduce

```sh
PYTHONPATH=src:scripts:.:analysis /workspace/fpl-venv/bin/python scripts/locked_numerical_runtime.py analysis/screen_role_transitions.py
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 /workspace/fpl-venv/bin/python -m pytest -q tests
```

`source-manifest.json` pins the scored implementation and numerical input archives. `tests/test_role_transition_evidence.py` checks unknown versus confirmed absence, return pressure, future/previous-club isolation, co-starters, target-label/duplicate/clock rejection and double-gameweek targets.

Validation: **997 tests passed** in the full local regression suite (58.16 seconds). Source hashes, chronological fit logs, frozen upstream reproduction and keeper invariance passed. This is local validation; no new deployment workflow was requested for a rejected candidate.
