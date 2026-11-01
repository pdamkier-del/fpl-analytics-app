# Observed competition context and calibration monitoring

**Implemented and tested as an explicit shadow path. Not activated in the B app or production.** This is not an xP improvement claim or a completed MM→PM→TS validation for the candidate.

## Delivered

- `scripts/competition_context.py`: one reusable cutoff-safe context contract, plus an opt-in adapter for the existing B calibrator. Workload follows verified player identity across transfers; role diagnostics remain club-specific. Missing game minutes are not converted to zero. Partial sums remain descriptive lower bounds; uncertain physical inputs use the existing missingness channels. Adapter joins require exact player/fixture/season/cutoff identity and normalize UTC clocks for downstream inference.
- `scripts/build_competition_context.py`: reads canonical all-competition match/player-event files. It uses canonical `team_id`, never provider `team_code`, and waits until actual capture time before making non-PL evidence available. It preserves the authoritative, possibly newer PL NUM inputs and adds only non-PL load: an older retained raw PL archive cannot overwrite fresh PL history or be counted twice.
- `analysis/screen_competition_context.py`: frozen historical comparison. The same C=.1 B calibrator is fitted before each origin with prior labels only, using matching candidate features in BOTH training and targets. No player exceptions, coefficient search or changes to hard absences, normal role, durations or tactical constraints.
- `analysis/screen_current_competition_context.py`: upstream MM comparison on all 669 players / 4,014 six-GW rows of the saved 24 October input snapshot. This is before final shared role/GK allocation; it is not the app's displayed final P(start), xM or xP.
- `analysis/score_prospective_player_forecast.py`: checks archived pre-deadline predictions against explicitly final results. It rejects wrong identities, late captures, duplicate labels and non-final matches; reports reliability, Brier/log loss, minute/point MAE and bias without fitting a correction.

Existing prospective publication capture is reused. No additional independent start probability is inserted into PM or TS. Role-shift statistics are diagnostics, not unsupported automatic boosts. The previous failed European-rest residual is not activated. Existing finishing and market research decisions remain unchanged.

## Fixed v2 historical result

The existing pre-role/GK B baseline was reproduced with maximum P(start) discrepancy **1.92e-9**. The same **27,092 player/fixture rows** were evaluated in both arms across two seasons GW22–38.

| Upstream MM metric | 2024/25 baseline → candidate | 2025/26 baseline → candidate |
|---|---:|---:|
| Minute MAE | 10.948646 → 10.899451 | 10.263079 → 10.256903 |
| Start Brier | .07230668 → .07227992 | .06794265 → .06801109 |
| Absolute minute bias | .332369 → .333997 | .217595 → .217863 |

The fixed numerical noninferiority screen passes. It does **not** establish a consistently better model: the mean minute gain is only .0492 / .00618 minutes, and start Brier worsens in 2025/26. The 2025/26 minute-MAE bootstrap interval includes no improvement, as do both start-Brier intervals. Rotation-minute gains are .0743 / .00973 minutes; both rotation intervals include zero. See `uncertainty.json`.

The non-PL-exposed historical cohorts are only 1,667 / 177 rows. Coverage and retrospective source-clock limitations remain explicit. Probability reports are upstream mean-preserving marginal diagnostics, before final role/GK kernels. Keeper rows use the generic upstream duration approximation in this diagnostic; they must not be presented as calibration of the final joint goalkeeper kernel. No downstream xP/TS candidate gate was run or passed. No candidate is promoted from these small upstream changes.

`lower-bound-diagnostic/` preserves the first nonpromotable v1 screen. V2 was fixed before its scoring because unknown minutes must not become measured zero load. The v1 output is not a fallback model. Parameters/gates were not relaxed after either result.

## Current input repair and evidence

Canonical raw sources contain 70 PL, 15 CL, 9 EL, 2 Conference, 2 Conference qualifying and 23 League Cup matches. The small GW player-stat CSVs omit non-PL games, so reading them alone would falsely suggest that CL/cup minutes do not exist. `current/coverage.csv` reports the full canonical event ledger. All retained starters have minute observations; some nonstarter minute fields remain unknown, not confirmed unused benches. Complete tournament-fixture coverage is not independently established.

The retained canonical capture is from **23 October**, while the reviewed target feature snapshot is from **24 October**. The adapter therefore adds its non-PL observations to authoritative PL NUM fields from the reviewed target, rather than replacing fresher PL evidence. Role diagnostics from the retained archive are descriptive and may lag newer PL evidence; they are not newly activated predictors.

`current/observed-events.csv.gz` preserves normalized public professional-player input evidence and its capture clocks. `current/manifest.json` records exact raw input hashes. Target input files come from numerical origin artifact run **40124214540**, forecast seal **6ebf56331e0575fb7252c2fd0384c49167075ab5c5937eecc16ce964ae4da273**. This experiment does not call the old snapshot fresh data on 25 October.

## Prospective validation

The retained real pre-deadline ledger contains 4,014 eligible rows. At the actual scoring time all target kickoffs are still in the future, so `prospective-monitor.json` correctly reports **pending final matches**, with null errors rather than fictitious zero errors. The new scorer is executable infrastructure, not a claim that future matches have already validated the candidate. It scores one specified forecast seal; aggregating several snapshots requires an explicit horizon/capture selection policy and must not count the same target as independent evidence repeatedly.

For completed matches supply a final-results CSV with season, exact fixture/player UUID, club, kickoff, final flag, actual starts, reported FPL minutes, points and the real result-observation time. Provider-created approximate points are not official final FPL labels. CLI:

```
PYTHONPATH=src:scripts:.:analysis python analysis/score_prospective_player_forecast.py --ledger path/to/archived-ledger --outcomes final-results.csv --out validation.json
```

## Promotion decision

Keep the best documented active B version. The new physical adapter remains opt-in. Required before activation: trustworthy current source coverage, prospective evidence, and the final shared role/GK MM→PM→TS and six-GW point/scenario gates. Unknown bench minutes are uncertainty; a CL start does not itself prove the next PL start or a causal rest explanation. Structured coach quotes and a timestamped market feed are not implemented by this change; existing market research did not establish a reliable incremental gain.

The known joint substitution-process issue remains separate and unresolved. Production, published B forecasts, manager squads and the desktop layout were not changed. No official FPL actions were performed.
