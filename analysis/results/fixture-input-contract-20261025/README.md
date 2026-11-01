# Shared fixture input: exact compatibility evidence

Baseline commit `fbfed1f`, before the contract extraction. `replay-fingerprints.json` is byte-identical to both the before and after receipts. It covers 50 current fixtures and 48 real historical fixtures, with ten draws each. Both the entire `MatchSimInput` (all mathematical parameters and player ordering) and all preview outputs, penalty decomposition and raw scenario arrays are hashed. No model training or parameter selection occurred.

`current-six-GW-inputs.json` separately checks ALL 60 fixtures, 4,014 rows and 669 players of the reviewed source snapshot: splitting/joining preserves every feature value and dtype exactly and every fixture prepares successfully. It must not be described as a new xP-quality test or a browser/deployment check.

Reproduce the replay with the existing archived source inputs:

```
PYTHONPATH=src:scripts:.:analysis python scripts/locked_numerical_runtime.py analysis/check_fixture_input_parity.py --current-pm path/to/exact/pm.csv.gz --out after.json --reference analysis/results/fixture-input-contract-20261025/replay-fingerprints.json
```

The current source file comes from numerical origin run 40124214540 and matches the SHA256 in `current-six-GW-inputs.json`. Historical source composition uses the existing `run_vfinal_integrated.build_final_frame`, unchanged by this refactor. The pure source-input construction was moved into `fixture_input.py`, with no calculation or coefficient change. Required missing rates, wrong clubs/cutoffs and ambiguous joins now fail explicitly. Legacy optional input defaults retain their prior presence flag and mathematical behavior.

The reviewed NP guard pins the shared contract and unchanged underlying adapters plus this fixed parity receipt. No guard was disabled and no historical acceptance threshold was loosened. Existing upstream MM and later role/GK/NP stages remain intact. No production or public B deployment is claimed.
