# Canonical fixture inputs — first integration slice (2026-11-02)

This branch adds an opt-in adapter. Frozen MM, PM, TS v3 and production callers remain unchanged.

## Ownership
- Match: fixture ID, cutoff, home and away team IDs, expected team goals and assist probability.
- Team: team ID, expected penalties and penalty conversion.
- Player: player identity, FPL position, event rates, card probabilities, saves and BPS background.
- Minutes: one canonical start probability, cameo probability, start duration, cameo duration and expected minutes.

The new canonical_fixture_input.py adapter validates required data and the identity:
xmins = p_start * start_minutes_mean + (1-p_start) * p_cameo_given_bench * cameo_minutes_mean.

It expands the existing control_* and v4_* aliases only when their values are identical; if they differ legitimately, the original explicit scenario-input path must be used. No hidden rate estimation or imputation is performed.

## Acceptance gates
1. Run pytest -q tests/test_canonical_fixture_input.py tests/test_fixture_input.py.
2. Test a real live fixture for equality between control and v4 minute inputs, keeping distinct experiments separate.
3. Compare serialized MatchSimInput from canonical and original adapters.
4. Compare seeded Monte Carlo outputs on the same frozen fixtures and measure xP parity.
5. Migrate live builders only after the parity gates pass.

This is an architectural first slice, not a production migration or a demonstrated xP improvement.
