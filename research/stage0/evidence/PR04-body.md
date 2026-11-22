## Result and recommendation

**Do not integrate the individual role MM. Preserve the original production MM.** This extends the existing experimental role modules on the existing branch; it does not replace the locked model. The 2,125-point benchmark and `locked_model_active=false` remain unchanged. PR #3's PM work is untouched.

The preselected starter-role arm improves minute MAE by only 0.018836 / 0.008276 minutes versus the identical logistic learner without role features (2024/25 / 2025/26). Incremental start-Brier and log-loss intervals include zero. Individual duration/cameo arms worsen minute MAE; continuous roles remain a separately evaluated alternative, without retrospective primary-model selection.

## Completed full PM comparison

Each season completed 330 captured fixtures × six MM/PM arms × 400 draws, with archived fixture seeds. Original baseline inputs/reference xP match exactly and all ten point components sum to xP. Evaluation below uses 2024/25 GW22–38 and 2025/26 GW6–38, including zero-minute rows.

| Period / PM | Original MM xP-MAE / RMSE | Logistic control | Selected role MM |
|---|---:|---:|---:|
| 2024/25 original PM | .947794 / 1.848146 | .935537 / 1.848219 | .934494 / 1.846749 |
| 2024/25 player PM v2 | .949547 / 1.843938 | .933284 / 1.841888 | .934657 / 1.843327 |
| 2025/26 original PM | .929173 / 1.880707 | .915176 / 1.874802 | .914609 / 1.875388 |
| 2025/26 player PM v2 | .929528 / 1.878570 | .915782 / 1.873742 | .915592 / 1.873055 |

Role-minus-control xP-MAE deltas and paired fixture 95% intervals:

- 2024 original PM: −.001043 [−.003548, +.001347].
- 2024 player PM v2: +.001373 [−.001444, +.004063].
- 2025 original PM: −.000567 [−.002562, +.001398].
- 2025 player PM v2: −.000190 [−.002252, +.001787].

All incremental MAE and RMSE intervals cross zero. Played-only xP-MAE worsens under PM v2 in both years. Reserve gains do not establish consistent starter/rotation or injury-return gains. PM v2 uses PR #3's fixed player hybrid configuration, without retuning.

## Audit and forecast limits

Unknown availability is never treated as confirmed availability. Past squad membership is reconstructed only after strict player/fixture/club reconciliation, with conservative known-time proxies. Missing medical labels prohibit claiming a verified injury-return result. Historical publication/registration clocks are not certified. Both seasons have been reused in earlier research and are **not independent holdouts**. Expected-XI constraints are enforced, while the legacy PM's independent realized-XI sampling is explicitly not certified.

Frozen-origin MM diagnostics through GW+5 are completed. They do not establish a calibrated future rest/injury trajectory or complete six-GW xP inputs. The historical forecast has only **33/183** required origin→target pairs. No TS replay or new strategy score was produced.

## Evidence and verification

- [Full audit, mathematics, MM/PM tables, subgroup and component analysis](https://github.com/pdamkier-del/fpl-analytics-app/blob/6d875a65251fb62f691dc0386ea81aeb29d27c0f/docs/audits/2026-10-15-individual-mm-validation.md).
- [Direct numerical summary](https://github.com/pdamkier-del/fpl-analytics-app/blob/6d875a65251fb62f691dc0386ea81aeb29d27c0f/analysis/results/individual-mm-20261015/summary.json).
- [Checksummed permanent evidence and restore instructions](https://github.com/pdamkier-del/fpl-analytics-app/blob/6d875a65251fb62f691dc0386ea81aeb29d27c0f/checkpoints/individual_mm_20261015/README.md): all scored MM/PM/horizon rows, full calibration and uncertainty reports, selection and source hashes; 17 verified files in a 13.5 MB capsule.
- **570 regression tests passed locally and in [CI run 38872310526](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38872310526)** on commit `6d875a6` (CI: 18.14 seconds). The five new merge/evidence tests also passed again after precision hardening. [Six-GW contract checks](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38872310540) passed their 24 regression tests and confirmed the historical input rejection; this is not a passing forecast coverage result.
- 2025 full PM completed in Actions run 38795223403. 2024 full PM completed locally from the exact restored remote research source, with strict 330-fixture shard merging. The earlier missing conditional-source folder is fixed in CI; run 38869721082 is a redundant replication, not a claimed completed CI result.
- Full historical replays are manually dispatched; ordinary regression checks remain automatic.

Research only. Keep this PR as a draft; no merge, deployment or model activation.
