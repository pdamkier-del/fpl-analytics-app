# Transfer Strategy v3 — rolling 6GW planner built

Point model remains locked. Chips are not part of TS v3.

## Mechanics
- Rolling/receding horizon: plan up to six visible GWs, execute only the first
  action, then re-plan next deadline with fresh forecasts/state.
- State is squad + bank + free transfers + each owned player's purchase price.
- Free-transfer dynamics are endogenous:
  FT_next = min(5, max(0, FT_now - transfers_now) + 1).
- Paid transfers cost the official 4 points plus the configured forecast-risk
  buffer in the decision objective. Default buffer = 1.5.
- Free transfers have no fixed 2.16-point option cost in TS v3. Banking value
  comes from carrying the larger FT state into future branches.
- Current deadline prices are frozen inside the hypothetical six-GW path, so
  future historical price changes cannot leak into the decision.
- Candidate squads optimize legal XI + captain separately for each visible GW.
  This lets the planner retain a player through bad fixtures, bench them, and
  use them later instead of forcing an unnecessary sell/buy-back cycle.
- Beam search keeps economic state distinct by squad, bank, FT and purchase
  prices. Candidate generation uses MILP and can branch over 0-5 transfers.
- Only the first transfer bundle is applied by execute_first_action.

## Implementation
- src/fpl_xpts/transfer_planner.py
- tests/test_transfer_planner.py
- .github/workflows/transfer-planner-v3-tests.yml

## Verification
Dedicated TS v3 tests plus the existing season-replay tests pass in workflow
run 37348763039.

Covered mechanics:
- FT banking and five-FT cap
- official hit cost and 1.5 uncertainty buffer only on paid transfers
- banking over multiple hypothetical weeks
- separate weekly lineup optimization
- execute-first-action-only receding-horizon behavior
- compatibility with existing replay mechanics

No season performance replay has been run with TS v3 yet. The next step is to
wire TS v3 into the replay harness and compare it against TS v2 under the locked
forecast model.
