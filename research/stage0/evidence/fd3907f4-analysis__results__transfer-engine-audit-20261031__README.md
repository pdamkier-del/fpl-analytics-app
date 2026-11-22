# Read-only transfer engine audit

No model, planner policy, public forecast, app deployment or official FPL action was changed.

Targeted regression run: 31 passed across transfer planner, joint transfer planner, WC action, B WC export, live TS bridge and future BB tests. A full current B calculation was privately replayed from officially reconciled ownership, historical purchase costs, cash, transfer ledger and chip state. All normal and WC-follow-up paths were independently checked for legal squads, sale/buy cash, free transfers, official hits, uncertainty buffer, shared-PM score, horizon weights and WC gain against the same normal path. The original input state remained unchanged. Personal inputs, rosters and results remain outside Git.

The audit helper is `analysis/audit_live_transfer_result.py`, run through `scripts/locked_numerical_runtime.py`. It rejects private state/result paths inside the repository.

Limits: this does not prove predictive accuracy or global optimality. Active fast-local ordinary candidate generation excludes negative weighted-player-value legs and restricts targets. WC proposals use top-two MILP squads under an eight-second-per-proposal limit before exact shared-PM path scoring; the proposer uses scalar xP, not full scenario policy. Existing scope limitations are not newly introduced regressions. See `docs/checkpoints/2026-10-05-ts-v3-targeted-diagnostic-setup.md`; its earlier hit-discount finding is already resolved in the active config (`discount_transfer_costs=False`). The current six-GW weights are (1, .6, .36, .216, .1296, .07776), not equal weights. Any private discrepancy with browser-local bank/FT/purchase costs still requires comparing that browser's saved state; public GW picks alone do not expose unpublished changes.
