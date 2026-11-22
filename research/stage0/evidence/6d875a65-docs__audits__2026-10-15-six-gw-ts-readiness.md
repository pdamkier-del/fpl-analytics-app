# Six-GW research track: current contract and remaining dependencies

This branch is **not** a production or historical-TS-certification branch.
It leaves locked MM/PM/TS, the 2,125-point reference, and
`locked_model_active=false` unchanged.

## Implemented

- `scripts/validate_six_gw_forecast.py` verifies the shape of a
  decision-GW → target-GW → FPL-player forecast table, including all six
  future horizon slots, unique rows, finite xP, and first-target roster
  continuity into all later targets.
- `scripts/rolling_deadline_state.py` takes the latest registered source
  and MM player state **at or before** the origin cutoff, rather than the
  latest state by GW number alone.
- `scripts/run_rolling_vfinal_gw6_38.py` now exports
  `forecast_contract.json` and a noncertification summary alongside the
  forecast. Its optional `--require-complete-horizon` fails after writing
  diagnostics if the contract is not satisfied.
- Dedicated historical-leakage/coverage regression tests and a read-only
  GitHub Actions workflow are provided.

## What these checks cannot prove

1. Historical actual publication timestamps are not in the source
   material: kickoff+3h in the inherited historical adapter is a proxy,
   not verified delivery time.
2. The six-week builder reuses the same origin-cutoff MM probability and
   duration for each scheduled future fixture. It does **not** project
   intervening games, player workload, new injuries, team news, or transfers.
3. A historical FPL player price/eligibility/registration ledger known at
   each decision cutoff is required to certify squad choices.
4. Blank-GW player targets and deadline-authoritative roster snapshots
   must be represented and reconciled. A missing target row must never be
   silently treated as zero xP.
5. The original 2,125-point replay uses the current GW at each origin
   (33 origin-target pairs versus 183 needed for a true six-GW GW6–38
   horizon). A re-run with six-GW forecasts is a **new benchmark
   experiment**, not proof that the original benchmark already had six
   weeks.

## Reproduce research checks

```sh
python -m pip install pytest pandas
python -m pytest tests/test_six_gw_forecast_validator.py tests/test_rolling_deadline_state.py -q
python scripts/validate_six_gw_forecast.py path/to/rolling_vfinal_forecast.csv.gz --report /tmp/sixgw-contract.json
```

The validator returns exit code 2 for missing or invalid required cells.
The research generator accepts `--require-complete-horizon` to reject
incomplete output. These are local commands: do not present them as passed
until CI finishes and logs are reviewed.

## Next research steps

1. Run the generator against checksum-pinned historical origin snapshots
   and inspect structural diagnostics. Preserve exact input hashes.
2. Implement an origin-date target-MM projection with explicit
   rest/workload uncertainty using only pre-origin information; validate
   against the *frozen-state* forecast before combining with PM.
3. Reconcile historical source publication, roster/price and all-BGW
   coverage. Keep unresolved fields unavailable, not invented.
4. Only after full origin/target/player coverage and provenance controls,
   use identical generated inputs to compare locked PM against PM v2 and
   the same TS planner. Report new totals independently from 2,125.
