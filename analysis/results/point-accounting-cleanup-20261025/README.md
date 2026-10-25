# Behavior-preserving point accounting cleanup

The baseline is commit `f4e0944`, before extracting the duplicate FPL point rules into `point_accounting.py`. The fixed comparison uses 100 real historical fixture inputs spanning both seasons, 20 full match draws and 20 aggregate draws per fixture. It compares every PlayerSimResult field, sampled intervals, final generator state after each draw, and every `simulate_many` output. Both full replay files have identical SHA256; see `verification.json` and individual fixture fingerprints.

Reproduce with the existing prepared historical task cache:

```
PYTHONPATH=src:scripts:.:analysis /workspace/fpl-venv/bin/python scripts/locked_numerical_runtime.py analysis/check_scoring_refactor_parity.py --tasks path/to/prepared-tasks.json.gz --out after.json --reference analysis/results/point-accounting-cleanup-20261025/replay-fingerprints.json
```

The task cache is the same seven-field tuples produced by `test_separated_goal_head.prepare_tasks`, with unused role distributions replaced by null for JSON serialization. These checks isolate scoring; they do not establish a new full-season forecast validation or solve joint substitutions. Role-assignment behavior remains covered by the existing tests.

The first full test run caught the intended NP source-integrity guard after `joint_simulator.py` changed. Following exact replay, its source hash was refreshed, the extracted module was added to the guard, and this fixed parity receipt was also pinned. The model, fitted weights, historical acceptance decision, protocol and seeds were not changed. The guard remains active; it was not bypassed.

The analytic PM/market experiment stays offline. Production and the active B publication remain pinned to their previous sources. This commit is an implementation cleanup, not a new model release. The original output API and goal/clean-sheet constants remain compatible with existing experimental callers.
