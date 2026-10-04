# Full-season origin and horizon coverage gate

Continues aab3a841346f28ba97552b17e96b8529094816b0. The opt-in season mechanics pass tests; no archived policy, simulator, scoring or forecasts are changed.

The original control file contains GW6–38 targets and no stored origin timestamp. The selected v4 file contains GW22–38 and explicit cutoffs. Matching those cutoffs to the recovered event calendar yields exactly 17 origin/target-GW pairs: each origin forecasts only its own GW. It contains no stored future-GW forecast at an earlier origin. A later deadline's forecast must not be borrowed as an earlier origin's forecast.

The existing strategy has up to six-GW visibility. Across 38 origins, truncated at season end, that requires 213 origin/target-GW cells. Only 17 are stored in the selected v4 artifact; 196 are absent. All GW1–21 v4 origins and GW1–5 control targets are absent. These are precise coverage facts about the selected artifacts, not proof that no historical development archive contains forecasts. Recover original origin-stamped outputs if available; otherwise generate them from as-of histories with frozen parameters and separately version their provenance. Never use later outcomes or tune on GW22–38 to fill these cells.

`analysis/results/season-replay-coverage-v1/deadline_coverage.csv` gives all 38 deadlines, available origin windows, missing horizon cells, retained joint fixtures, blocked roster rows and recovered price-snapshot coverage. `manifest.json` separates six gates: roster evidence, forecasts, historical prices, mechanics integration, historical scoring and as-of fixture schedules. Price snapshots currently cover only GW22–38.

Several future deadlines change across the recovered snapshots. The audit calendar deliberately takes the latest recovered event metadata; it is not advertised as a predeadline schedule. Changed event IDs are listed in the manifest. As-of BGW/DGW schedules remain an independent data/integration gate.

125 tests remain green from the mechanics checkpoint. Coverage output reproduces byte-for-byte, and all source/checksum and archived strategy checks pass. The previously completed 144-fixture paired diagnostic remains technically successful and unchanged. Full-season readiness is false: neither a 38-GW replay nor a rolling decision replay can be justified by silently reusing these target-only forecasts. The concrete roster source gap also remains 32 rows across 26 fixtures.

Next resume with an independent timestamped roster source or recovered original fixed-origin forecast archive. Season mechanics still require an explicit, paired orchestration integration; scoring requires a separately versioned 2025/26 profile and declared missing-event treatment. Do not restart reconstruction or rerun the completed paired diagnostic to resolve these missing inputs.
