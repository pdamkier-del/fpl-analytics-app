# TS v4 joint rolling MILP — build checkpoint

## Status

Built and tested on branch `audit-role-minutes-20261001`. No full-season TS v4
replay has been started.

Primary implementation:
- `src/fpl_xpts/transfer_planner_joint.py`
- tests: `tests/test_transfer_planner_joint.py`
- real-data GW1-only smoke: `scripts/run_ts_v4_joint_smoke.py`

## Mechanism

TS v4 keeps the intended receding-horizon policy but replaces candidate/beam
search with one joint MILP per deadline.

For the visible six-GW horizon the solver jointly chooses:
- 15-player squad in every GW;
- buys and sells;
- bank path;
- exact free-transfer state and 0–5 transfers per GW;
- official paid-transfer hits;
- XI, captain and vice captain separately in every GW.

Only the first action is intended to be executed; the problem is solved again at
the next real deadline.

There is no fixed saved-FT value. FT value is endogenous through exact state
transitions:
`FT_next = min(5, max(0, FT_now - transfers) + 1)`.

The objective uses horizon weights only on forecast manager points. Official hit
cost and hit uncertainty buffer are deterministic and are not horizon-discounted.

## Search freedom

There is no TS v3 fast-local candidate generator:
- all players in the current metadata universe are eligible;
- every transfer count 0–5 is feasible each hypothetical GW;
- no individual transfer leg must have positive xP gain;
- cheap enabler/downgrade legs are allowed when they finance a better joint bundle;
- no top-18-per-position candidate filter;
- no 12-candidate-per-depth filter;
- no outer path beam.

The MILP itself searches the feasible space subject to FPL squad, club, budget,
lineup and FT constraints.

Frozen deadline prices are used throughout the hypothetical horizon. Initial
owned players retain their true FPL sale value until sold. A player bought during
the hypothetical path is tracked separately and later sells at the frozen current
price, preserving exact purchase/sale accounting under the frozen-price rule.

Captain/vice fallback is represented inside the MILP, matching the existing
manager-score logic rather than optimizing captain xP alone.

## Verification

The dedicated TS v4 joint-planner workflow completed successfully.

Unit coverage includes:
- endogenous FT banking/cap behavior;
- a two-transfer budget restructure where one individual downgrade loses xP but
  finances a much stronger premium upgrade;
- literal official hit/buffer accounting;
- 0–5 transfer cap.

A real-data **GW1-only** smoke test also completed successfully. This was not a
season replay.

GW1 smoke:
- visible horizon: GW1–6;
- solver runtime: **36.82 s**;
- objective: **207.8495**;
- first action: **0 transfers**;
- bank unchanged;
- solver produced a legal six-GW path.

For comparison only, the earlier TS v3 GW1 objective was ~207.84 and also
executed 0 transfers, so the new formulation is not showing an obvious GW1
plumbing discontinuity.

At roughly this scale a 38-deadline replay is computationally plausible (order
of tens of minutes rather than the failed v3.1 many-hours path explosion), but
later deadlines may vary. A full season has deliberately not been launched yet.

## Next step

Before any full-season run, wire this planner into a dedicated replay runner with:
1. forced club-transfer FT accounting fixed rather than inherited;
2. checkpoint/resume;
3. per-GW solver status/runtime/mip-gap logging;
4. invariant checks for budget, squad legality, FT transitions and hit accounting;
5. unchanged point model and chips OFF.

Then run the season only after explicit go-ahead.
