# MM experiment A: individualized slow-changing starter role

Status: **research-only implementation; no historical superiority established**.
The locked MM and experimental start/survival MM are unchanged.

## Hypothesis

A player's recurring starting role should not be erased by a single cameo,
short tactical substitution, or absence while not available. Sustained
benching while available may indicate a genuine role change.

## Candidate

`scripts/experimental_individual_role_mm.py` computes a Beta-style,
calendar-decayed empirical prior for starting **conditional on being verified
available**. Unknown availability and out-of-cutoff matches provide no role
evidence. A player's prior mean and pseudo-sample strength regularize sparse
history. Parameters are provisional and must be tuned on development periods,
never on Haaland or João Pedro target examples.

This is an **input feature for a candidate MM**, not a substitute for
`P(available)`, role competition, official starting-XI constraints, or the
existing starter-duration/cameo model. Specifically, it should not be
multiplied into the old start probability without a separately calibrated
fusion rule. A role prior near one does not imply guaranteed starts.

## Required tests before integration

1. Create observations available strictly before each historical deadline;
   distinguish verified player absence from a tactical bench appearance.
   Verify that the historical availability field is timestamp-correct;
   unknown status must remain unknown rather than masquerading as availability.
2. Compare frozen original MM, previous experimental logistic/start-survival
   MM, and original MM plus role feature under an identical, legal-XI
   framework. Train/tune on earlier fixtures, evaluate later seasons, with
   uncertainty by fixture and club.
3. Separate role-transition false alarms, post-injury returns, high-minute
   regulars and rotation specialists. Report start Brier/log-loss, minutes
   MAE/RMSE and calibration, not only illustrative player cases.
4. Analyze whether the role feature brings independent signal beyond
   existing MM historical starts/minutes; remove it if redundant.
5. Run full PM xP tests before considering six-GW TS. Do not change production
   `locked_model_active=false` or the 2,125-point benchmark.

## Reproduce current unit tests

```sh
python -m pytest tests/test_experimental_individual_role_mm.py -q
```

CI result must be inspected before claiming verified pass.
