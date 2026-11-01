# Finishing and receiver-weighted assists: investigation

The request is to investigate individual finishing beyond xG and assist conversion weighted by the likely finishers on the pitch. No application/model publication or private manager calculation is part of this investigation.

## Result

There is already relevant completed research. Its historical results do not justify enabling a new PM. The exact creator→receiver variant cannot be identified from the current source set: shotmaps have no creator ID on unsuccessful attempts. A lineup/exposure-weighted approximation is possible, and is already represented in the opt-in player PM v2. It remains a research approximation, not an observed passing network.

The read-only `scripts/investigate_finishing_receivers.py` now verifies 24 archived reports against their manifests and recomputes current finishing/receiver sensitivity. The report is `analysis/results/finishing-receivers-20261020/feasibility.json`. It uses read-only Core history plus existing current-season observations, excludes unavailable/future observations and the known early-2022/23 expected-stat placeholders, and binds the calculation to the served planning forecast `ee4c118518d14792af49e34beda13642ef9b7e61dbba9ef2073b0635b5c39b93`, observed 20 October 2026 16:23:21 Copenhagen. Focus players are selected by stable IDs with team/name checks, because web names are not unique.

## Fresh sensitivity, not new forecast accuracy

Existing finishing estimator: Gamma/Poisson neutral prior of 20 xG, decaying historical goals and xG, cap [0.75,1.25]. No hyperparameters were selected using the following focus results.

| Historical weighting | Saka conversion factor | Cole Palmer conversion factor |
| --- | ---: | ---: |
| 90-day half-life | 0.97316 | 1.00356 |
| 365-day half-life | 0.96936 | 0.99942 |
| 730-day half-life | 0.98655 | 1.01300 |

The corresponding unweighted available histories are 42 goals / 40.3405 xG and 49 / 46.42. These all-xG ratios include penalties; they do not identify non-penalty finishing skill. The data does not support assuming a large persistent Saka finishing deficit. Multipliers above apply to conversion, not directly to total xP, and changing allocation/total/bonus requires a full coherent PM replay.

For the next fixture, a crude receiver approximation weights each teammate's 730-day finishing factor by original goal rate × PM expected minutes, excludes the creator and uses only pre-match quantities. Saka's receiver factor is 1.00055, Palmer's 1.05178. These are sensitivity factors, not calibrated assist or point gains. Expected exposure is only a proxy for joint co-presence; no observed pass→shot links are invented.

A common team multiplier cancels if applied to every player's normalized assist weight while the total assist budget is fixed. The script checks this algebra. Finisher quality must affect the chance→goal/assist process coherently, once, rather than simply multiply all normalized assist shares. xA observations should remain intact; the conversion layer predicts realized goals/FPL assists.

## Already completed historical evidence

`docs/checkpoints/2026-10-15-player-pm-v2-completed.md` and `docs/audits/2026-10-15-player-pm-v2.md` describe the individual chance/finishing profiles and actual active-lineup intensity. `experimental_player_pm.lineup_rates` explicitly uses a goal-contribution-weighted finishing average among the exposed players, with optional creative contribution and unchanged separate penalty process. Its resulting goals feed the joint goal→assist event and full BPS/point calculation. It does not learn creator-specific recipient links.

Historical xP MAE, original locked MM, original versus the selected hybrid player PM (lower is better):

| Evaluation | Original | Hybrid |
| --- | ---: | ---: |
| 2024/25 GW22–38 | 0.947794 | 0.949547 |
| 2025/26 GW6–38 | 0.929173 | 0.929528 |

These are recovered verified results, not newly run historical tests. The primary player-PM matrix used 330 fixtures per season/MM arm and 400 draws; the development selection used earlier 2024/25 GW6–21. The periods have been used in previous research and are not pristine holdouts. Finishing-on/off attribution helped one period and hurt the other. The later dynamic/legal-XI matrix also failed to establish a robust improvement. The related conversion-only study did not justify replacing PM either.

## Data limitation and decision

Core has no native multi-season npxG or shot counts in these fields. The previous raw audit found 380 verified 2024 PL shotmaps with 9,883 shots, but creator IDs only on some successful goals. Those links alone would condition on success and cannot identify creator→receiver chance conversion. Different-provider penalty xG is not subtracted from FPL xG without equivalence evidence. The historical kickoff+3/4h publication proxies remain a limitation.

Keep the deployed models unchanged. Individual finishing and lineup-aware conversion are plausible mechanisms, but the archived tests and current sensitivity do not establish an improvement. The exact new receiver hypothesis needs all-attempt creator/receiver data or an explicitly labelled approximation evaluated on fresh validation. The previously identified current penalty-role discrepancy is a separate defect and must not be credited as a finishing improvement.

Validation this investigation: 24 archived JSON hashes checked; 17 focused conversion/finishing/source/attribution tests passed. The read-only audit completed successfully. No newly simulated historical xP improvement or personal transfer-plan gain is claimed.

Reproduce (use the existing successful full-run artifact 39437545079 for the matching forecast and PM input):

```bash
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/investigate_finishing_receivers.py \
  --live-history data_v1_1/derived/live_locked_inputs/2026-27-v1/player_fixture_observations.csv.gz \
  --forecast /tmp/fpl-capacity-fresh-model/current/forecast.json \
  --pm-input /tmp/fpl-saka-palmer-evidence/current-B-inputs/pm.csv.gz \
  --out analysis/results/finishing-receivers-20261020/feasibility.json
```
