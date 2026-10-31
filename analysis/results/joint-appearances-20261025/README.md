# Shared appearance budget: tested, not activated

The first optimization step tested a bounded correction to the existing B
MM → PM process. Existing whole role lineups, goalkeeper hierarchy/durations,
ordinary/penalty separation and reported-duration laws remain in use. There
are no new fitted parameters or named-player adjustments.
The five-substitution budget assumes a standard match; concussion and other
exception allowances are not introduced by this candidate.

The candidate jointly rounds bench participation under a shared maximum of
five appearances, reserving one slot if the sampled goalkeeper is replaced.
Feasible conditional cameo probabilities are preserved. A lineup whose
conditional probabilities sum above its remaining budget gets proportional
reductions. This is an explicit candidate hypothesis: it does **not** prove
the original aggregate player marginals could not be retained by a different
allocation across lineups. No reported-minute sum-to-900 constraint is used.

## Historical result

341 fixtures / 27,092 player-fixture rows, both seasons GW22–38. The selected B
baseline reproduces saved xP exactly. Each arm uses 400 joint draws per fixture.
These are reused research periods with the original historical availability
proxies, not an independent prospective validation.

| Metric | 2024/25 B → candidate | 2025/26 B → candidate |
|---|---:|---:|
| Minute MAE | 10.912877 → 10.912398 | 10.184831 → 10.185258 |
| xP MAE | 0.889075 → 0.892471 | 0.870893 → 0.870272 |
| Start Brier | 0.072177 → 0.072177 | 0.067899 → 0.067899 |

The fixed numerical noninferiority screen passes, but a consistent predictive
improvement is not established. The 2024/25 realized xP-MAE increase is
+0.003396 (paired fixture bootstrap 95% [0.000717, 0.005945]); the 2025/26 change
is −0.000621 [−0.003231, 0.002031]. These intervals include the realized
400-draw differences and do not substitute for a separate Monte Carlo
convergence test. Rotation/played errors and all biases are in `metrics.csv`.

Crucially, this is only an appearance-budget correction. It does not pair
outgoing and incoming players or certify active-player coverage or three
substitution windows. The protocol forbids publication from this partial
candidate alone. `activated=false`, `publishable=false`; the active B and
production models remain unchanged, including their known timeline limitation.

## Minute-error diagnosis

For outfield players, xM minus observed minutes is exactly the signed sum of
start selection, starter duration, cameo selection and cameo duration terms.
The mean absolute component sizes are:

| Component, minutes | 2024/25 | 2025/26 |
|---|---:|---:|
| Start selection | 11.269 | 10.889 |
| Starter duration | 2.636 | 2.288 |
| Cameo selection | 2.803 | 2.595 |
| Cameo duration | 1.374 | 1.274 |

Absolute component sizes are **not additive shares of MAE**, oracle gains or
proof that all start uncertainty is avoidable. They identify start/role evidence
as the more material research priority; this experiment leaves those start
probabilities unchanged. `start-reliability.csv` reports final B outfield start
reliability. Keeper replacement weights are excluded from this decomposition.

All 57,030 final historical Core rows have missing `sub_on_second` and
`sub_off_second`. This does not rule out obtaining event clocks elsewhere; it
means this archive cannot by itself validate a new physical-to-FPL minute
conversion. Do not relabel the old physical 900-minute experiment as validated.

## Reproduction

Use the existing environment with `PYTHONPATH=src:scripts:.:analysis`:

```sh
python scripts/locked_numerical_runtime.py analysis/screen_joint_appearances.py --out analysis/results/joint-appearances-20261025 --workers 2
python analysis/summarize_joint_appearances.py --out analysis/results/joint-appearances-20261025
python scripts/locked_numerical_runtime.py analysis/check_current_joint_appearances.py --artifact /path/to/origin-40124214540 --forecast /path/to/reviewed-forecast.json --out analysis/results/joint-appearances-20261025
OPENBLAS_NUM_THREADS=1 python -m pytest -q tests
```

The current rehearsal must use the **same origin archive** for live goalkeeper
history as for the other model inputs. An initial mismatch correctly failed
the exact-reference guard; the local retained live table contained 70 matches,
while the origin archive contained 74. No tolerance was relaxed and no input
date was advanced. The reviewed forecast and model remain untouched.

The corrected archived rehearsal passes for all 60 fixtures / 669 players /
4,014 rows, GW9–14, with exact baseline xP reproduction. Candidate goalkeeper
coverage, appearance-count bounds and shared PM/TS scenario means pass. This
does not test the full TS optimizer's transfer decisions. All 980 regression
tests pass. An additional 100-fixture default-path replay retains exact player
events, intervals, RNG state, aggregates and shared preview scenarios. See
`verification.json`, `current-six-GW.json` and `default-path-parity.json`.
