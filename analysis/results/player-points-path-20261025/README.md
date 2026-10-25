# Inspectable data-to-points trace

`player-traces.json.gz` contains all 669 players and 4,014 player/fixture rows of the **saved reviewed 24 October B release**, not a new current forecast. Its content seal is `6ebf56331e0575fb7252c2fd0384c49167075ab5c5937eecc16ce964ae4da273`.

Every row follows `upstream_PM_inputs → selected_NP_head → MM → PM → TS`. The four original input file hashes and the exact selected NP allocation file hash were verified against the sealed forecast. Existing identities, MM/PM means, full horizon, aligned TS sample mean and every point-component sum were checked. This is an explanation/integrity tool, not a refit, causal feature-attribution method or certification of future forecast accuracy. No private manager state is included.

See `summary.json` for input and artifact hashes and `docs/model/data-to-player-points.md` for the maintained code ownership map and CLI usage. Data is retained compressed because the trace repeats shared source context for each player/fixture.
