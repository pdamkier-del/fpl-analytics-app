# TS v3 targeted diagnostic setup

Target: explain the TS v3 gap to TS v2 before changing mechanics.

## Static code audit: two concrete structural differences

### 1. Fast-local candidate generation can exclude joint budget restructures

The TS v3 fast-local proposer ranks players by summed weighted player xP and
currently rejects any individual transfer leg with negative weighted-player gain:

`gain = value(in) - value(out)`
`if gain <= 0: continue`

Therefore a multi-transfer bundle cannot contain a deliberate low-xP downgrade
to release budget for a larger upgrade elsewhere. Cheap enablers can also be
absent because only the top 18 weighted-xP targets per position are considered.

This is materially different from TS v2's joint MILP, which optimizes the whole
15-man squad, XI and captain under a joint budget and can accept a weak individual
leg if the complete bundle is better.

The local beam then returns only the top 12 squads at each exact transfer depth,
ranked by summed individual player-value gain rather than lineup-aware manager
score. The outer TS v3 scorer is lineup-aware, but it cannot recover a squad that
the proposer never returns.

This is now the leading candidate-coverage hypothesis.

### 2. Future deterministic transfer costs are horizon-discounted

Current TS v3 objective adds:

`weight_k * (manager_score_k - official_hit_k - uncertainty_buffer_k)`

Thus the deterministic official hit and buffer are discounted with forecast
points. Under baseline weights a paid transfer at GW+5 has a nominal decision
cost 5.5 but contributes only 1.375 to the path objective.

A diagnostic config switch was added with the default unchanged. The alternative
uses:

`weight_k * manager_score_k - official_hit_k - uncertainty_buffer_k`

This lets us isolate cost accounting without changing the point model.

## Targeted experiment

Script: `scripts/run_ts_v3_gw2_8_diagnostic.py`

For GW2-GW8 it reconstructs the actual baseline TS v3 pre-deadline state and:

1. runs the baseline rolling planner;
2. runs the same planner with undiscounted deterministic transfer costs;
3. applies the TS v2 static lineup-aware optimizer to the SAME TS v3 state;
4. checks whether that exact static-optimum squad appears in the fast-local
   candidate set;
5. forcibly injects that static squad as the first action and measures the
   resulting six-GW TS v3 path objective;
6. logs first-action changes and retrospective current-GW actual scores.

The true TS v3 baseline action alone evolves the state, so all comparisons at
each deadline share the same pre-state.

The workflow is queued because earlier long-running replay jobs are still
occupying GitHub Actions capacity. No production defaults have been changed:
`discount_transfer_costs=True` remains the default.
