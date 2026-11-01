# Reproduce the isolated precision audit

Reference application/model: `736d65cacc1afeeaf8c3dcfad317d7ee745b48fa`.
Read [the single report](../../docs/2026-11-01-systematic-precision-audit.md) and
[protocol](../results/systematic-precision-audit-20261101/protocol.json) first.
No script in this directory activates a model or publishes the application.
The frozen historical inputs explicitly contain outcomes for oracle diagnostics;
never expose them as a real forecasting endpoint.

Python 3.12, `pip install -r requirements-model-checkpoint.txt pytest requests`.
From the repository root:

```bash
export PYTHONPATH=src:scripts:.:analysis
AUDIT_WORK=/tmp/fpl-systematic-precision-audit
AUDIT_RESULTS=analysis/results/systematic-precision-audit-20261101
mkdir -p "$AUDIT_WORK"
cp "$AUDIT_RESULTS"/inputs/* "$AUDIT_WORK"/
python -c 'import gzip,pathlib; p=pathlib.Path("analysis/results/systematic-precision-audit-20261101/prospective"); pathlib.Path("/tmp/fpl-systematic-precision-audit/current-forecast.json").write_bytes(gzip.decompress(next(p.glob("forecast-*.json.gz")).read_bytes()))'
pytest -q tests/test_precision_audit_oracles.py tests/test_precision_audit_prospective.py tests/test_precision_audit_decisions.py tests/test_b_event_conservation.py tests/test_physical_timeline.py tests/test_gk_solo_role.py
python scripts/locked_numerical_runtime.py analysis/precision_audit/runner.py --inputs "$AUDIT_WORK/historical-inputs.json.gz" --out "$AUDIT_WORK/baseline" --mode baseline --workers 2
python scripts/locked_numerical_runtime.py analysis/precision_audit/runner.py --inputs "$AUDIT_WORK/historical-inputs.json.gz" --out "$AUDIT_WORK/oracle" --mode oracle --workers 2
python scripts/locked_numerical_runtime.py analysis/precision_audit/runner.py --inputs "$AUDIT_WORK/mc-inputs.json.gz" --out "$AUDIT_WORK/mc" --mode mc --workers 2
python -m precision_audit.report --work "$AUDIT_WORK" --out "$AUDIT_WORK/summary" --part all
python -m precision_audit.supplement --work "$AUDIT_WORK" --out "$AUDIT_WORK/summary"
python -m precision_audit.decisions --work "$AUDIT_WORK" --out "$AUDIT_RESULTS" --mode historical-frozen
python scripts/locked_numerical_runtime.py analysis/precision_audit/decisions.py --work "$AUDIT_WORK" --out "$AUDIT_WORK/summary" --mode mc
python -m precision_audit.prospective --out "$AUDIT_RESULTS/prospective" --verify-only
```

Heavy runs are resumable: one hashed gzip result per fixture/seed/arm, invalidated
by input or simulator-source changes. Original run: 341 baseline fixtures × 3,
48 oracle fixtures × 8 × 3, and 14 MC fixtures × 6. Prefixes are not additional
independent simulation draws. Several tens of minutes on the audit machine;
worker count affects wall time, not seeds. Raw NPZ sample matrices are regenerated
by `runner`, not committed as an extra 43 MB of duplicate draws. Receipts' saved
`REGENERATE:<hash>.npz` names identify the originals; a rerun records its new paths.
Use the same locked launcher for numerical work; saved timings are measurements,
not reproducible constants.

`historical-frozen` verifies all six historical FT cases against saved decisions
using the archived prices, legal initial states and aligned joint sample matrices.
It needs no manager history, Core DB or network. It does not overwrite the
historical case report. `--mode historical` reconstructs those inputs from the
original local Core/archived bootstrap data; it is not necessary for replay of the
frozen evidence. Original source clocks and survivorship limitations are disclosed
in the report. `dataset.py` records how the frozen simulator inputs were built;
raw-provider reconstruction requires the repository's historical data collection
workspace. Do not substitute a later live API response for missing old inputs.

For an independent one-fixture numerical identity check:

```bash
python scripts/locked_numerical_runtime.py analysis/precision_audit/runner.py --inputs "$AUDIT_WORK/historical-inputs.json.gz" --out "$AUDIT_WORK/smoke-baseline" --mode baseline --workers 2 --limit 1
python -m precision_audit.verify_replay --actual "$AUDIT_WORK/smoke-baseline/predictions.csv.gz" --reference "$AUDIT_RESULTS/raw/baseline-predictions.csv.gz"
```

CI does this baseline check and all eight oracle arms, plus source isolation, tests,
prospective seal/chain verification and result checksums. It uploads the evidence
with 90-day retention. The committed forecast and hashes persist after artifact
expiry. This is explicitly a CI smoke replay, not a second full 341-fixture run.

The frozen predeadline group table permits reproduction of medical, cup/UEFA and
role summaries without today's source responses. `parameter-provenance.json`
discloses what parameter-fit timing cannot be established. Historical research
periods remain reused and 2024 NP coefficients are nonchronological.

Results: `raw/` retains every player/seed/arm metric; `inputs/` contains public
historical fixtures and current model evidence, no personal manager state.
`mc-control-cases.csv` and `current-control-components.csv` cover named controls.
`oracle-group-metrics.csv`, `event-calibration.csv`,
`individual-season-calibration.csv.gz` and `minute-error-structure.csv` contain all
position/role/player/club groups. `fixture-sampling-uncertainty.json` differs from
seed-noise estimates. `SHA256SUMS` covers the committed evidence.
