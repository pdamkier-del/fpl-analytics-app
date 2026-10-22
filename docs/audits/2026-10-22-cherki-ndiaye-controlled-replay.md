# Controlled latest-PL observation ablation: Ndiaye and Cherki

The requested diagnostic is complete. It measures sensitivity, not whether the probabilities are accurate. No B forecast, original model, production file, private manager state, or public deployment was changed.

Frozen baseline: archived 22 October 2026 08:16:18 UTC public input run 39745524857, artifact 12414535468. This is slightly later than the currently served 07:40 PM source. Original raw observations were restored separately from the SHA-verified diagnostic-39741134035-1 checkpoint (07:32 source), without overwriting repository source data. Reconstructed B PR4/PR9 features agree with the archived target to maximum absolute difference 7.79e-8. Baseline P(start), analytic minutes, and original-seed xP reproduce the archived numerical forecast; xP is exactly reproduced for both focus players.

## Controlled interventions

Historical role-model and PR9 training samples remain fixed. The original upstream MM outputs, archived normal-role memory/duration carry, current news, opponent, PM event inputs, and goal/assist allocation inputs remain fixed. Each intervention removes the relevant player observation from the latest PL fixture (17 October, Ipswich), rebuilds PR4 prefix/role features and PR9 prior features, then reapplies the original fitted models and exact team projections. This is the complete **B feature path** under fixed upstream inputs, not a refit of the full original upstream MM. Removed records and input/source hashes are retained in the JSON receipts.

Five arms: unchanged baseline; omit Ndiaye; omit Cherki; omit both; replace only their PR9 `last_started` indicator with its preceding observed value (Ndiaye remains 1, Cherki changes 0→1). The last arm is an explicit input sensitivity probe, not a claim that Cherki started the match.

| Arm | Ndiaye P(start) | Ndiaye xM | Cherki P(start) | Cherki xM |
| --- | ---: | ---: | ---: | ---: |
| Frozen baseline | 87.66% | 79.58 | 46.55% | 45.63 |
| Omit Ndiaye's latest observation | 80.09% | 75.52 | 47.25% | 46.19 |
| Omit Cherki's latest observation | 87.29% | 79.39 | 55.39% | 52.77 |
| Omit both latest observations | 79.56% | 75.24 | 56.10% | 53.34 |
| PR9 last-start indicator only | 87.43% | 79.46 | 52.17% | 50.17 |

The latest observation changes Ndiaye's marginal by about +7.57 percentage points, and Cherki's by about −8.84 points in their respective single-removal contrasts. Removing both reduces their marginal gap from 41.11 to 23.46 percentage points. Team projection couples competitors, so individual contrasts are not additive and marginal probabilities are not a head-to-head choice. The last-start indicator alone accounts for +5.62 points when Cherki is switched to the preceding start indicator, with all other B features fixed. These are diagnostic contrasts; they do not isolate only the numerical 90-minute duration from all other facts of the match.

The latest match therefore materially widens the gap. It is not the entire explanation: without both observations, Ndiaye still has the higher start probability. The replay neither proves the weight excessive nor establishes that Cherki should outrank Ndiaye.

## PM simulation and verification

Original unified B minute sampler and original PM are used for all arms. Exact MM and PM analytic minute means agree. The bridge asserts exact equality of every non-minute PM input; team starter marginal totals remain 11, and the existing simulator checks joint goalkeeper coverage. News caps and actual available roster are preserved.

Eight seeds × 400 match draws × five arms = 16,000 match draws. Repeated-seed mean xP:

| Arm | Ndiaye xP | Cherki xP |
| --- | ---: | ---: |
| Frozen baseline | 3.800 | 2.487 |
| Omit Ndiaye | 3.454 | 2.719 |
| Omit Cherki | 3.793 | 3.034 |
| Omit both | 3.547 | 3.003 |
| Last-start indicator only | 3.763 | 3.062 |

These are repeated-seed diagnostic means for the frozen 08:16 inputs, **not replacements for the app's single-run 07:40-source xP**. The detailed JSON includes per-seed values and standard errors. Paired seeds are not event-aligned; contrasts retain Monte Carlo variation. In particular, Cherki's xP differences between the three favourable interventions are not evidence that lower minutes increase his underlying rate. Frozen PM inputs do not mean other teammates' on-pitch outcomes are fixed.

32 relevant regression tests passed in 4.77 seconds. Diagnostic baseline-reconstruction, archived original-seed equality, non-minute equality, legal starter totals, and MM/PM mean checks all passed. No held-out start-Brier, minute-MAE, xP-MAE or bias improvement is established by this one-fixture sensitivity test. No CL-informed rest inference was introduced and the factual observation was not erased from a live model.

## Reproduction

Read-only implementation: `analysis/diagnose_latest_pl_start.py`. Restore the specified GitHub evidence artifact and verified checkpoint into separate directories, retain the existing verified role-training cache, then run:

```bash
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 /workspace/fpl-venv/bin/python \
  analysis/diagnose_latest_pl_start.py \
  --evidence /tmp/cherki-pm-audit/evidence \
  --source /tmp/cherki-pm-audit/source \
  --out analysis/results/cherki-pm-diagnostic-20261022 --repeats 8
```

Results: `analysis/results/cherki-pm-diagnostic-20261022/controlled-replay.json`; source and test receipt: `controlled-replay-receipt.json`. The earlier observational snapshot comparison is in `2026-10-22-cherki-pm-diagnostic.md`.
