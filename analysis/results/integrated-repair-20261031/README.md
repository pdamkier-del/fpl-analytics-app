# B source and event repair — two-season evidence

Repairs persistent unavailable players, physical workload train/inference semantics, dated return uncertainty and shared own-goal/scorer accounting. Production, fitted NP head and locked TSv3 remain unchanged. Existing PR #22 / integration branch retained.

## Final joint MM→PM replay

341 fixtures, 27,092 player-fixture rows per arm, 400 draws, both seasons GW22–38. Frozen physical B baseline reproduced exactly: **maximum xP error 0**. These are reused research periods, not independent certification. Full metrics/fixture-bootstrap intervals: [pm/result.json](pm/result.json); event calibration bins: [pm/event-calibration.csv](pm/event-calibration.csv).

| Season | Model | Start Brier | Minute MAE | xP MAE | xP bias |
|---|---|---:|---:|---:|---:|
|2024/25|Previous B|0.072177|10.91986|0.890843|+0.003916|
|2024/25|Events only|0.072177|10.91986|0.890478|−0.004229|
|2024/25|Source + events|0.072112|10.88206|0.889531|−0.004086|
|2025/26|Previous B|0.067898|10.29107|0.875883|+0.023739|
|2025/26|Events only|0.067898|10.29107|0.873386|+0.016016|
|2025/26|Source + events|0.068008|10.29447|0.873200|+0.014967|

Combined xP-MAE changes: −0.001312 (95% fixture bootstrap[−0.004220,+0.001759]) and −0.002683 ([−0.005242,−0.000160]). No claim that every metric improves: second-season start/minute errors increase slightly; first-season absolute xP bias increases slightly. Physical accounting is a correctness requirement, not an arbitrary performance tune.

Goal bias/player improves +0.001820→+0.000852 and +0.002731→+0.001545. Assist bias moves +0.000069→−0.000823 and +0.000151→−0.000933: absolute assist bias worsens slightly. Do not claim complete assist calibration. No assist retuning was activated to conceal missing special-event mechanisms.

The corrected shared score includes about 0.083 own goals/match in this simulation. Maximum conditional inclusive-goal budget error 4.44e−16, zero unattributed goals. Ordinary scorer/assist validation fails closed. Own-goal and penalty-winner assist attribution rules are tested, but occurrence rates require unavailable calibrated source evidence; no invented assister. Red-card removal process remains outside the normal-match physical kernel. Active B already used conditional on-pitch penalty conversion; this repair retains it and checks it together with own-goal mass.

## Sources and scope

[workload/result.json](workload/result.json) is the separate raw-MM feature-stage test; do not substitute its metrics for the final joint results above. Same feature computation for historical training/current inference; frozen v1 feature-parity check retained. 2024/25 includes 3,252 mapped non-PL observations, including substitutes; 2025/26 uses the audited recovered cup/UEFA subset. Coverage is partial and historical availability clocks retain documented +3/+4h proxies. Current/ historical physical ledgers and medical-training records are sealed with each forecast.

[medical/result.json](medical/result.json): 512 dated episodes / 1,738 monthly walk-forward horizon forecasts. Better Brier than always-available and still-out baselines. Label is **first recorded PL appearance**, not medical clearance or a guaranteed start. Unambiguous source-known dates only; insufficient risk sets marked Not Available. This validation is distinct from the above start/minute replay.

Persistent eligibility across all six GWs applies to all positions. Explicit exits/season loans and ambiguous status-u remain distinct. Latest source can supersede earlier exclusions. Current source 15:07UTC on31October has 106 status-u players (95 explicit exits/seasonloans, 11 ambiguous); all receive 0 minutes/points throughout GW10–15. The earlier issue cohort had 85 confirmed departures: snapshots differ.

Upcoming relative match importance remains neutral. No eligible predeadline historical non-PL calendar was established; retrospective finished-match records cannot supply it without leakage.

## Rejected / retained alternatives

[team-goals/result.json](team-goals/result.json): fixed 14-xG shrinkage of prefix G/xG worsens team-goal Poisson NLL in both seasons (1.47612→1.48430;1.43061→1.43194). Keep current team model. Its mean goal bias/team fixture is+0.01886 and+0.06131; no evidence of broad severe overprediction. Previous attack-budget studies independently rejected replacing normalization with raw individual rates; no named-player tuning.

[ts/result.json](ts/result.json): bounded synthetic exact diagnostics demonstrate a financing bundle missed by the candidate generator (12 weighted-player-value units net of a 4-point hit), and a joint XI/bench/C/VC score 74 vs 72.25. These are search limitations, not demonstrated current-manager regret or full-season gains. Existing TSv3 retained; no unvalidated search activation. Exact 3300-policy enumeration costs about 2.7 seconds for just one synthetic 15-player squad, before repeated path evaluation.

## Current local verification

Actual source cutoff 31 October 2026 15:07UTC; 669 players, 60 fixtures, GW10–15. Final forecast/repeat byte-identical; one-match and one-GW distributions exactly match six-GW seeds. Synthetic six-GW TS/chips passed without changing manager state. Python 1,111 passed; JavaScript 31 suites passed. Original PM oracle retains exact seeded events/RNG/aggregate parity on 100 full-roster plus 100 original fixtures. [current-player-comparison.json](current-player-comparison.json) is the **same-source local** control, not a comparison across weeks. Point differences include Monte Carlo order changes. Public CI creates a fresh same-source comparison for the published forecast.

Publication and actual desktop/mobile verification are pending; this file does not claim deployment. [evidence.json](evidence.json) seals numerical source/evidence. No manager roster, ID or private plan is included.

Reproduce with `PYTHONPATH=src:scripts:.:analysis` and the fixed numerical runtime. Restore verified Core, MM role/injury and2024/25 checkpoints first. Run `analysis/validate_b_workload_repair.py`, `analysis/validate_b_medical_return.py`, `analysis/validate_b_integrated_repair.py` (without `--tasks`, it rebuilds original tasks), then current pipeline/stages and `analysis/validate_b_repair_release.py`. Research results do not activate production.
