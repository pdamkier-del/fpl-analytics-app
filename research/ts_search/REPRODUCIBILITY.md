# Reproduce EXP-TS-SEARCH-001

Original implementation commit:`9f9ae6e3`; preregistered running checkout:`759ccf51`. The original registry JSON remains unchanged; events record actual implementation and results. All inputs are synthetic; no private manager files, Core database, matches, forecast fetch or fit needed.

## Offline verification from the result PR

```sh
python research/tools/registry.py validate
OPENBLAS_NUM_THREADS=1 python research/ts_search/code/verify_results.py research/results/EXP-TS-SEARCH-001/initial-run/results.json
python research/ts_search/code/summarize_results.py
OPENBLAS_NUM_THREADS=1 python -m pytest research/tests research/stage0/tests research/ts_search/tests -q
```

The verifier checks original implementation/input hashes and independently replays recorded chosen paths; it does not rerun TS or assert optimality merely from a feasible path. The renderer only regenerates the case table, summary and source-based pruning witnesses from archived results. Original results are never overwritten by those commands.

## Full exact-suite reproduction in a fresh isolated worktree

The runner intentionally requires the registered **running** state and refuses nonempty output directories. After completion, use the original running checkout rather than resetting the canonical registry or changing protocols:

```sh
git worktree add --detach /tmp/ts-search-registration 759ccf51
git worktree add --detach /tmp/ts-frozen-numerics 161b67b6fb8786a38e78c245b92a03ad841575d8
cd /tmp/ts-search-registration
OPENBLAS_NUM_THREADS=1 /path/to/python research/ts_search/code/run_experiment.py \
  --frozen-root /tmp/ts-frozen-numerics \
  --out /tmp/ts-search-reproduction-new-directory
```

Install the pinned-source numerical requirements in a dedicated environment, with numpy/pandas/scipy/scikit-learn; the recorded initial environment used Python3.12 and the versions in the result. All 532 original Python files are checked before loading. No current app code is imported from the result branch. The source config is imported unmodified and all its fields compared to the manifest. The exact study has no RNG; float-reduction order/platform may create tiny rounding differences, so compare objective/gaps with the original 1e-9tolerance, not runtime or JSON-byte identity. Runtime/environment fields vary by machine.

The delivered initial run was a single42-case execution in 16.095455 seconds under a120-second process wall timer. No full second run was performed. Any later reproduction is the **same experiment**, not42 new independent tests. Do not silently enlarge bounds, alter payoffs/menu or extend a timed-out initial budget.
