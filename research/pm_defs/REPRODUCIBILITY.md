# PM definitions: reproduction and evidence scope

Start with `catalog.v1.json`, `ledger.schema.v1.json`, `CATALOG.md` and the result report. All data/code hashes used by the application are fixed in the initial implementation manifest and its v2 successor. Existing source receipts are byte-preserved; none is relabelled a new accuracy experiment.

```sh
python research/tools/registry.py validate
python -m pytest research/tests research/pm_defs/tests -q
python research/pm_defs/code/render_catalog.py
```

These tests/views do not run MM, PM, TS, old calibrations or decompositions. The renderer regenerates only its readable catalog/coverage views from the saved contract-application result. Do not edit already anchored result evidence.

The executable compatibility application uses existing tracked GW8–10archives and compact PR32receipts, not a Core database or private manager files. It checks source hashes, original publication/finality and new point-ledger/unit/partition contracts, then writes field-presence counts and separately labelled imported old evidence. It uses no RNG, model import or fit.

Original implementation/catalog commit:`34f7049b`. Registration and running commit:`a39bd217`. Its preflight rejected a string `__file__` passed to a Path-only checksum helper **before** any archive application; `attempt-1-blocked.json` preserves this. The v1code remains unchanged. Fixed v2code, manifest and re-registration were committed at`74809fd7`before application. Only path coercion and manifest filename changed; all catalog/schema/input/contract/test bytes remained unchanged.

For a full reapplication of the **same schema regression**, use the registered running checkout in a new worktree; the canonical completed registry is never reset:

```sh
git worktree add --detach /tmp/pm-definitions-registered 74809fd7
cd /tmp/pm-definitions-registered
python research/pm_defs/code/run_contract_audit_v2.py --out /tmp/new-pm-definition-result
```

Use a fresh output directory. No third-party Python dependency is needed for the application; pytest is needed for tests. Numerical archive values are not regenerated. Output runtime is machine-dependent. Run failure details and all final results are preserved; metadata/contract reapplication is not independent future evidence.

Additional pure contract helpers (`partition_contract.py`, `identifiability.py`) make same-target BPSreplacement and fixed-binary-award identification explicit. They are tested without rerunning the application, changing its frozen input or claiming new forecast validation. Point coefficients are also compared to the already archived official machine config in unit tests. The scripts are research contracts, not a complete substitute for official point adjudication, provider rights or historical event-time evidence.

`source_sha256` hashes the input artifact bytes; it does not replace the original semantic forecast hash. Raw-provider availability is inherited metadata; provider raw shot data is not shipped or newly distributed. Public sports-data access does not establish general redistribution rights. No actual substitutions-trial status/capture/scoring action is triggered by any command above.
