# Target-equivalent attack budget diagnostic — decision: retain live model

This is the calibrated extension declared before the full original cohort was scored; see the sibling `attack-budget-ablation-20261031/calibrated-extension-protocol.json`. The same 341 fixtures, 1,091 distinct players and 27,092 player-fixture observations per arm were evaluated. Both seasons are reused GW22–38 research diagnostics, not independent validation.

Individual xA is converted to expected FPL assists using current-season prior-known FPL-assist/xA totals with 50 prior xA of shrinkage to earlier seasons. Blend weight stays fixed at .5. No parameters are tuned to named players or candidate scores. The complete original current baseline predictions are reused exactly; calibrated candidates use the same physical MM kernel and existing joint scoring/bonus engine. Separate penalties and legal match constraints remain in place. No production model source file is changed; no candidate is activated in the app.

| Played-player metric | Current 2024/25 | Blend 2024/25 | Individual 2024/25 | Current 2025/26 | Blend 2025/26 | Individual 2025/26 |
|---|---:|---:|---:|---:|---:|---:|
| xP MAE | 1.884003 | 1.894034 | 1.913815 | 1.988008 | 1.997536 | 2.008830 |
| xP RMSE | 2.752561 | 2.763142 | 2.788088 | 2.832227 | 2.843091 | 2.857166 |

All-player RMSE also worsens in both seasons. Individual all-player RMSE deltas have positive fixture-bootstrap intervals in both seasons; blend deterioration is clear in 2024/25 and inconclusive in 2025/26. Smoothing the common assist probability alone is mixed/negligible across seasons. Thus none of these fixed variants is a documented broad improvement. This does not prove all possible individual or hybrid models inferior.

An exploratory, *baseline-defined* xP>=5 subgroup has 83 and 72 rows. Current bias is +0.8803 and +0.4762 points, respectively. Its 95% fixture-bootstrap intervals are [0.0904, 1.6561] and [-0.4659, 1.3056]. The calibrated blend reduces this subgroup's point error, but the tiny previously examined group is insufficient to select a live calibration rule. Component decomposition attributes the positive mean error mainly to goals and partly bonus/other points; aggregate assist point bias in this subgroup is negative. Therefore globally lowering assist expectations is not supported by this diagnostic.

## Reproduce

Use the existing restored Core database and original research source archives, not newly fetched target outcomes in forecast preparation. The helper regenerates missing prepared tasks with the existing separated-head preparation code; it records the task archive checksum. `conclusion.json` also records the canonical task semantic checksum and final source hashes.

```sh
PYTHONPATH=src:scripts:.:analysis OPENBLAS_NUM_THREADS=1 /workspace/fpl-venv/bin/python scripts/locked_numerical_runtime.py analysis/research_attack_budget.py --out analysis/results/attack-budget-ablation-20261031 --workers 2
PYTHONPATH=src:scripts:.:analysis OPENBLAS_NUM_THREADS=1 /workspace/fpl-venv/bin/python scripts/locked_numerical_runtime.py analysis/research_attack_budget.py --out analysis/results/attack-budget-calibrated-20261031 --workers 2 --calibrated-reference analysis/results/attack-budget-ablation-20261031/predictions.csv.gz
```

The earlier sibling source receipt records the initial script before the calibrated mode and cache regeneration were added. The final script retains the same raw-arm mathematics and provides both modes. No historical score or parameter was overwritten to manufacture a gain.

## Practical findings

The current model already had João Pedro's injury and zero minutes/points; the incorrect suggested lineup in chat was an assistant error. Jackson's xM combines an approximately 85% start probability with conditional starter duration around 78 minutes, so 66.5 xM is not an assumption that he plays only 66.5 when starting. Barry's 5.08 season xG in 682 minutes versus Haaland's 6.09 in 709 means comparing only their scored goals is misleading. The earlier raw MGW xA comparison also mixed targets: current official totals were 203 FPL assists versus 143.92 xA.

Verified remaining scope gaps: explicit workload/last-start features are PL-only while tactical starter-role history includes other competitions; structured coach statements are not implemented; BPS history has partial coverage. These limitations are not proof of a specific causal error. TS cash/FT/hit and shared-score accounting passed the private audit, while its heuristic candidate restriction can miss budget-enabling bundles and it exposes little decision uncertainty. None of those is fixed by removing team goal allocation.

Next priority is a predeclared, chronological calibration study for high predictions with goal/bonus decomposition and uncertainty reporting, plus separate all-competition workload and candidate-coverage work. These must be evaluated rather than selected from the 155 high-xP rows above.
