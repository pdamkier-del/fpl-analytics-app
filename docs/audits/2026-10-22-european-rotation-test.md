# European rotation and role recovery: historical B-MM → PM test

The user requested a general historical test before introducing a CL/European rest explanation. This is an offline research candidate on the existing PR #22 branch. No finishing adjustment is introduced; the earlier finishing studies did not justify changing PM. Numerical preview and production remain unchanged.

## Candidate and frozen protocol

The protocol was written before results were inspected: `analysis/results/europe-rotation-20261022/protocol.json`. Frozen B is the reference. The candidate adds a regularized logistic residual to B's start logit using past European minutes, actual observed rest, recent European start/unused-bench status, and a prior-PL-nonstart → subsequently observed European-start interaction with the preceding PL role. No player names, Cherki exceptions, hand-set start boosts, target outcomes or future realised fixtures are used. Conditional starter/cameo durations and all PM event-rate inputs are held fixed. Exact team starter projection and injury/news caps are reused. Competitors can move because start probabilities share a legal team total.

Fits are prequential: only target labels strictly known before each origin enter training. The existing historical kickoff+4h/3h availability proxies remain explicit. Seven previously recovered original 2025/26 European team-games are reused with the later of the kickoff proxy and archived Git source version time; unknown starters stay unknown. Source maps are exact player identity/PL kickoff/club joins, and old-club European games do not become new-club role evidence.

L2 settings 0.1, 1, 10 are compared only on 2024/25 GW14–21. The selected setting is 10. Evaluation is 2024/25 GW22–38 and 2025/26 GW6–38. Those periods have already been used in project research; this is not an untouched independent holdout. Missing European records remain neutral/missing, not confirmed nonparticipation. Outcome and future-calendar mutations, late publication, unknown minutes, duplicate identity and club transfers have explicit tests.

## Scope limitation established before numerical evaluation

A complete historically captured future European fixture calendar is not available in the restored input set. Using the next realised European match from a post-season archive would create hindsight leakage. Consequently this test measures **role recovery after already observed European participation and recent workload**, not the full prospective hypothesis “a CL game is coming, so this player may be rested in the preceding PL match.” That latter component is not validated by this experiment and is not claimed implemented.

The 2025/26 European archive remains much sparser than 2024/25 even after the seven recovered games. The archived workload's independent fixture quarantine is retained. Original source publication/ingestion timing is not independently certified. These are explicit release limitations, not evidence of no European rotation effect.

## Reproduction and artifacts

- `scripts/research_europe_rotation.py --stage mm` builds historical features, performs prior-only fits and frozen development selection, writes minute/start predictions and the fit log.
- `scripts/research_europe_rotation.py --stage pm --workers 4` uses the same 501 archived original PM fixtures. It recalculates both arms for 135 affected fixtures and reuses exact reference draws for 366 unchanged fixtures. All baseline player xP and sampled-minute means must reproduce the archived unified reference exactly.
- `scripts/audit_europe_rotation_results.py` independently verifies source hashes, prior clocks, identities, exact-11 totals, hard absences, metrics and fixture-paired xP intervals. Its focused recovery table excludes goalkeepers, whose predictions the candidate deliberately holds fixed.
- Reports/predictions/protocol/fit logs/source hashes: `analysis/results/europe-rotation-20261022/`.

Results and final decision are recorded below after the PM and regression checks complete.

## Results and decision

**Decision: retain the current B model. Do not activate this candidate.** The fitted European residual slightly improves overall start Brier and minute MAE in both evaluated seasons. The small pooled start-Brier gain has a fixture-bootstrap interval below zero. However, point gains are not established, the intended recovery subgroup worsens in the stronger 2024/25 sample, and the next-season recovery/European coverage is insufficient. This does not establish that European context has no value.

Same 501 fixtures and 39,264 player/fixture rows per arm:

| Metric | 2024/25 baseline → candidate | 2025/26 baseline → candidate |
| --- | ---: | ---: |
| Start Brier | 0.07230668 → 0.07217136 | 0.06708364 → 0.06706309 |
| Analytic minute MAE | 10.94864562 → 10.94666346 | 10.13768766 → 10.13667779 |
| Minute bias | -0.33236881 → -0.32789842 | -0.25795323 → -0.25782001 |
| xP MAE | 0.88911980 → 0.88854941 | 0.90328625 → 0.90342549 |
| xP bias | -0.01054750 → -0.01006677 | 0.00352556 → 0.00419655 |

The focused outfield recovery cohort contains 91 rows in 2024/25 and only 11 in 2025/26. In 2024/25, start Brier worsens 0.21904 → 0.22781, minute MAE 29.3913 → 29.7503, minute bias +2.2720 → +4.5921, and xP MAE 1.66033 → 1.70453. The candidate can overprotect a player whose PL nonstart was genuine selection evidence. No fixture cause was labelled confirmed rest merely from this pattern.

In 2025/26 the focused start/minute metrics improve, but focused xP MAE worsens 2.17864 → 2.19886 and 11 rows cannot establish reliable recovery calibration. Broader European-context start Brier improves in both seasons; that is a different claim from successful recovery-role handling.

Overall fixture-paired 95% intervals for xP-MAE change include zero: 2024/25 [−0.002110, +0.000944], 2025/26 [−0.000701, +0.000977]. Match sampling variation and reused research data further limit inference. The loose aggregate PM noninferiority gate passes; that does not imply demonstrated predictive improvement.

Simulation: 135 affected fixtures × 2 arms × 400 draws = 108,000 new match simulations; 366 unchanged fixtures reuse exact archived draws for both arms. The two-season original unified baseline is reproduced exactly for every player xP and sampled-minute mean. No new transfer-plan accuracy or full-season TS return claim is made, and no personal manager state is used.

Regression: `PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 /workspace/fpl-venv/bin/python -m pytest -q tests`: **812 passed in 93.18 seconds**, including seven new chronology/identity/missing-data tests. The independent numerical/source audit passes prior-clock checks, source hashes, exact roster identity, MM mixture identities, exact-11 starter totals and hard news constraints.

No numerical preview publication is appropriate for this result. Production, the existing app, PM finishing assumptions, MM/PM minutes, and the public B forecast are unchanged. The complete future-calendar rest hypothesis remains an explicitly unvalidated component; no retrospective calendar has been backfilled as if historically known.
