# Research checkpoint — candidate duration sampler (2026-10-17)

**Status: NOT CERTIFIED; production unchanged.**

This branch extends PR #16 with a research-only minute sampler, **not** a live MM → PM → TS activation. The original locked `joint_simulator._sample_minutes` remains unchanged.

## What is implemented

- `scripts/mm_locked_bridge.py`: optional B/PR13 conditional minute sampling with cached distributions; explicit start, cameo and no-appearance paths. Conditional means are designed to equal B's `s`/`c` and the total mean to equal `p*s + (1-p)*q*c`.
- `simulate_candidate_pair`: single-process, scoped patch for a paired original-sampler / candidate-PMF **research** replay through the real match simulator; restores the original sampler afterward.
- `scripts/replay_mm_candidate_sampler.py`: runnable historical 2025/26 GW22–38 B-input replay with identical fixture/player pool, scoring labels and Monte Carlo budget. A smaller GW22 smoke test is in the branch workflow.
- `tests/test_mm_locked_bridge.py`: endpoint, validity, event-contract, hook restoration and deterministic mean checks.

## Validation restrictions and blockers

The historical replay **has not been shown to finish successfully in this conversation**. The GitHub connector returned no associated PR-triggered workflow runs for the latest branch commits; this is not confirmation of success or failure. This candidate remains unscored.

Existing PR13/15 minute PMF coverage and proper-scoring calibration gates have **not passed**. The Gaussian clip's mean defect is real, but fixing that mean does not automatically improve FPL point MAE. No consumer should switch samplers until the paired historical replay, calibrated intervals, appropriate Monte Carlo uncertainty, and untouched prospective validation are documented.

The current-role/availability/return feature producer and real current B → PM → TS app routing from PR #16 remain unfinished. This PR does not claim to solve them.

## Suggested execution

```bash
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/test_mm_locked_bridge.py
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/replay_mm_candidate_sampler.py --gws 22
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/replay_mm_candidate_sampler.py
```

Research results stay in `analysis/results/mm-pmf-sampler-research-20261017/`, never in the public app. Treat any point improvements as reused-history diagnostic only. Production remains on its previously locked sampler.
