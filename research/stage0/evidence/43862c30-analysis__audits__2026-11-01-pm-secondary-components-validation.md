# Secondary PM validation — 1 November 2026

Follow-up to [the source audit](2026-11-01-pm-secondary-components.md), based on
`audit-pm-secondary-components-20261101` at
`20dfdd953ef99c382ea969836cd6a514b8182cc4`.

## Decision boundary

Only one narrow source defect is eligible for repair: B's inclusive-save reserve
must be conditional on the defending keeper's own on-pitch interval. The repair is implemented in the explicit opt-in adapter
`experimental_keeper_save_reserve.py`. No CS, save-rate/tilt, DC or
BPS-background parameter is refit. The reused historical
cohort and incomplete inherited parameter-fit clocks cannot establish a robust
new empirical candidate or independent accuracy improvement. No production,
preview, lock, TSv3, original simulator or separate MM/assist branch is activated
or changed.

## Documented keeper reserve defect

`lambda_saves` is the keeper model's FPL-counted inclusive saves mean, not a
non-penalty-only mean (`keeper.forecast_fpl_save_mean`,
`deadline_keeper.keeper_saves_at_deadline`). Penalty saves correctly count once in
regular save-point buckets and also receive their separate five-point award.
That accounting is preserved.

B already integrates the active taker law when computing a team's scored-penalty
budget. However, its regular-save subtraction used the *whole-match* mean
conversion for every keeper. If taker conversion changes at the same time as a
keeper substitution, those keepers face different penalty-save opportunities.
The old subtraction preserves the pooled team mean but shifts saves between
keepers.

For keeper interval I and penalty conversion c(t), the required reserve is

```
E[PK saves in I] = lambda_opponent_penalties * P(save | miss)
                  * integral_I (1 - c(t)) dt / 90
regular save mean = max(0, lambda_saves * minutes/90 - E[PK saves in I])
```

The opt-in correction integrates the *same* hierarchy/history fallback and weights used
by B's event sampler, only over that keeper's interval. A full-90 keeper retains
the established calculation and random-number stream. Constant taker conversion
also retains the old conditional mean. No extra random numbers are consumed.
The count distribution still applies any configured save-bucket tilts afterwards;
those intentionally alter the pre-tilt mean. All frozen GK inputs have no tilts.

A deliberately strong test uses penalty rate 1, save-on-miss probability 1,
first-/second-half taker conversion .1/.9, and two 45-minute keepers with inclusive
lambda 2 per 90. Each keeper's target is 1 save. The original expectation is
1.2/0.8; the correction is exactly 1/1. At 10,000 draws the original means are
1.1984/0.7957, while the corrected means are .9812/.9956 (MC SE .00977/.00999).
The full-90 keeper is draw-for-draw identical, mean 1.9938, MC SE .01417.
Across the simulated cases, the maximum discrepancy from the corresponding
analytic mean is below 1.93 MC SE. This is a semantics test, not historical
accuracy evidence. Variable Poisson consumption means shared seeds alone do not
guarantee full eventwise common draws after an affected draw.

A zero inclusive lambda with positive explicit penalty-save opportunity has a
positive physical lower bound: regular saves floor at zero and the explicit
penalty saves remain. This is an incompatible input target, not a reason to
remove a real penalty-save event or its points. The test covers stable/switching
keepers, lambda 0/2, swapped and constant conversions, save thresholds >=3/6/9,
save points, PK-save points and joint bonus/BPS sensitivity.

## Historical evidence

See the [reproducible evidence and label limitations](../results/pm-secondary-components-20261101/README.md).
The original source audit is retained unchanged. Detailed component metrics,
reliability bins, dependency-cluster intervals and MC convergence are committed
alongside the forecast rows and source/input hashes.

### Cohort and checks

171 fixtures in 2024/25 and 170 in 2025/26 produce 27,092 known player-fixture
forecasts. Every known forecast player joins to an actual observation; no GK
training timestamp reaches its forecast cutoff. This does **not** establish the
training chronology of inherited fixed coefficients. Unlisted-keeper placeholders
are excluded from accuracy metrics. The first 400 draws reproduce the previous
audit exactly on 28,210 matched player/seed rows across all 341 fixtures, for
minutes, CS, save/DC/PK-save/conceded/negative points and bonus. Sources were
hashed before and after the full run and are identical.

### Clean sheets and conceded deductions

Independent direct player-CS labels remain **NOT AVAILABLE**. All player-CS
results below are rule-derived from the actual player's FPL minutes and conceded
count; direct GC counts are available. CS bias across GK/DEF/MID and both seasons
ranges from -0.525 to +0.299 percentage points, and every position-season
fixture-cluster interval spans zero. This does not prove all probability bins or
subgroups calibrated. The detailed tables include pregame P(60+), xM, opponent
lambda deciles, actual-minute buckets, club and individual diagnostics.

Team CS is a separate endpoint:

| Season | Team observations | Predicted CS | Actual CS | Brier |
|---|---:|---:|---:|---:|
| 2024/25 | 342 | 24.920% | 24.854% | .177535 |
| 2025/26 | 340 | 25.569% | 25.000% | .180182 |

There is no justified global team-lambda/CS adjustment. Conceded deductions use
actual player conceded counts and `-(gc//2)` for GK/DEF. Actual substitution
seconds and a full red-card exit/liability mechanism are unavailable; synthetic
own-goal events immediately before, exactly at, and after a 60-minute substitution
verify the half-open on-pitch boundary. They do not validate historical event
timestamps that the dataset does not contain.

### Saves and point buckets

The full roster includes reserve keepers and DNPs. For the most confident
pregame group, P(60+) > .95:

| Season | Keeper rows | Mean saves predicted / actual | Save points predicted / actual |
|---|---:|---:|---:|
| 2024/25 | 154 | 2.8553 / 2.8636 | .6260 / .5974 |
| 2025/26 | 164 | 2.6301 / 2.6220 | .5532 / .5488 |

Across the full labelled GK roster, saves biases are +.0303 and -.0285;
save-point biases +.0110 and -.0086. Their fixture-cluster intervals span zero
in both seasons. P(saves>=3) is 14.158%/13.377% predicted/actual in 2024/25 and
10.718%/11.429% in 2025/26. The >=6 rates are 2.455%/2.242% and 1.398%/1.429%.
Only four labelled rows reach nine saves, and only seven have a positive PK-save
count (eight saved penalties total). Neither tail supports a new tilt or global
rate adjustment. The results include source/keeper/club/opponent-lambda groups,
threshold reliability and finite-N noise; the documented conditional-reserve
repair above is not selected by fitting these outcomes.

### Defensive contributions

2024/25 direct DC labels are absent and the scoring adapter disables DC. In
2025/26, actual point awards, rather than inferred third-party counts, give:

| Position | Rows | Predicted hit | Actual hit | Bias, fixture-cluster 95% CI |
|---|---:|---:|---:|---:|
| DEF | 4,531 | 7.417% | 7.703% | -.286pp [-.952, +.397] |
| MID | 6,286 | 5.379% | 4.136% | +1.243pp [+.783, +1.721] |
| FWD | 1,560 | 1.091% | .385% | +.706pp [+.393, +.980] |

The MID signal deserves prospective testing. FWD has only six actual awards and
is explicitly sparse. None is an untouched-label improvement demonstration.
All 849 available rows within two actions of the 10/12 thresholds agree with
the official point-award labels. Thus this is a distribution/role calibration
question, not evidence that thresholds should be changed. The tables separate
xM, pregame participation, club/prior and actual-minute groups; no DC parameter
is changed.

### Bonus/BPS

Every fixture has a complete actual-participant BPS/bonus roster. Reapplying
joint bonus tie allocation to actual BPS produces **zero mismatches in all 341
fixtures**. Top-BPS tie frequencies predicted/actual are 6.589%/4.094% in
2024/25 and 7.089%/7.647% in 2025/26. The mean number of bonus recipients is
3.168/3.164 and 3.183/3.182. These fixture-level checks complement the per-position
P(1/2/3 bonus) reliability tables; pooled recipient counts alone do not prove the
right players receive bonus.

In 2025/26 the full-roster GK bonus bias is -.0209 points (fixture-cluster CI
[-.0374,-.0044]), while DEF is +.0147 [+.0038,+.0259]. GK BPS bias is -.3926
[-.6283,-.1705]. In the P(60+) > .95 GK group, BPS is 12.3397 predicted versus
13.5122 actual, and bonus .1675 versus .2561. This exposes a position-specific
research question that aggregate total bonus cannot resolve.

On actual participating rows with an identifiable generated-event partition,
the 2025/26 GK partial-background residual is underpredicted by 1.4738 BPS.
Observed residual variance / model background variance is .686 for GK, while
2024/25 FWD is 1.783. There is no basis for one global variance increase. Grouped
residual bias/spread is provided by season, position, minutes, team score, CS,
red card, assists and goal-count band. 2025/26 scoring rows have only residual
bounds because the penalty-goal split is absent; brace-conditioned exact
residual variance in that season remains **NOT AVAILABLE**. Rare red-card/brace
cells must not drive tuning. No 2026/27 labels are used to validate a different
season's BPS rules, and no BPS/bonus parameter is changed.

### Monte Carlo and acceptance

On the prespecified 14-fixture deep cohort, independent 10,000-draw seeds give
per-player RMS differences of .00452 save points for GK and .00358-.00628 bonus
points across positions. CS probability RMS differences are .00215-.00286.
The committed convergence tables show 400/2,000/10,000 prefixes and independent
seeds; score tables include Brier/log-loss/MAE/bias on that same cohort. Log loss
clips probabilities at 1e-6 and can remain sensitive to sampled zero tails:
2024/25 GK CS log loss on seed 0 is .3962/.3898/.2780 across the three N values.
Do not select a component candidate from a 400-draw tail discrepancy.

The accepted change is the analytically documented keeper-stint reserve repair
as an **isolated opt-in implementation**. The complete test suite revealed that
`b_event_simulator.py` is sealed by the approved nonpenalty policy. Updating that
shared source would invalidate the policy. Therefore the sealed simulator and
all existing policy hashes remain byte-for-byte unchanged. The adapter compiles
that simulator's body, checks for the audited expression, and replaces only the
keeper reserve; it fails closed if the expected source structure changes.
The context manager restores the previous B simulator even on failure. No
production, preview or default research path imports or enables the adapter.
The historical signals in MID/FWD DC and GK BPS/bonus are retained as diagnostic
findings, not fitted changes. A prospective lock/evaluation or genuinely untouched
cohort is still needed before choosing new component parameters. There is no
claim of independent end-to-end accuracy improvement from this reused cohort.
