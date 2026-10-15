# PM conversion research: completed checkpoint

Branch: `model-audit-optimization-20261012`, PR #3. Production remains on `free-github-static-20261010`; no merge or deployment is authorized by these research results. `locked_model_active=false` and `promotion_allowed=false`.

## Completed evidence

- Primary numerical code: `08ff78a066b341d56e07087d9c4536a6a05fc1c2`.
- All six jobs in [38717540912](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38717540912) passed: development selection, four historical arms, and frozen-current diagnostics.
- Each historical arm replays 330 fixtures at 400 draws. Locked reference outputs reproduce exactly in the two locked-MM arms. The experimental-MM arms use their own unchanged-PM baseline and intentionally do not claim equality to old-MM outputs. Eight PM arms under locked MM; three under the same experimental MM. Hyperparameters selected only on 2024/25 GW6–21.
- Five complete reports recovered byte-for-byte and SHA-256 verified in `analysis/results/pm-research-20261015/evidence_manifest.json`.
- Extra team-goal paired intervals and cutoff-safe role/team groups: [38720669600](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38720669600), success. `additional_calibration_report.json` is postprocessing only.
- Local regression suite: **519 passed in 21.76s**. Full audit [38720239913](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38720239913) passed at `7c16891`. Export checkout-order fix is `9c7ecbb`.

## Decision

Do not replace original PM. Assist-only conversion has a small consistent assist-log-loss gain and 2025 point-MAE gain, but uncertain 2024 point effect and mixed subgroup/BPS results. Combined PM does not reliably improve the experimental-MM reference. Finishing-adjusted team intensity worsens 2024 point-MAE with a paired interval excluding zero. More complex hierarchy/joint models do not establish a robust overall improvement.

Current diagnostics are frozen at **2026-10-12 10:45:27 UTC**, not a current 15 October forecast. Haaland original/combined xP: 5.68156/5.63031; Saka: 5.57219/5.56531. Chelsea lambda: 1.34286882 fixed versus 1.39585108 experimental adjusted-total. These are eight-seed means, not forecasts to publish over the app's original snapshot.

## Remaining constraints

Historical actual publication times, BPS/MM source completeness, equivalent multi-season non-penalty xG and event labels, independent new holdout and sufficient Monte Carlo precision remain unresolved. GW6 Chelsea source is provisional. Only 33/183 audited historical six-GW origin-target cells exist, so no candidate TS total is claimed. Preserve the 2,125 / 44-transfer / 28-hit-point benchmark.

Full report: `docs/audits/2026-10-15-goal-assist-model-research.md`. No private manager data was used, published, or modified. Do not rerun the completed main matrix just to recover its summaries; full reports are now committed, with source run and hashes.
