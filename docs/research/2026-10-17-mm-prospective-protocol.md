# Prospective MM validation protocol — version 1

This protocol is recorded before any new evaluation outcomes. It adds evidence
requirements; it does not relax the existing PR14/15 gates. Production stays
unchanged and `locked_model_active=false`.

## Registration and eligibility

Freeze the candidate code, upstream feature producer, parameters and data
contract before the first scored deadline. Each origin must have a witnessed
GitHub Actions artifact containing the actual prediction bytes, SHA-256,
code/input hashes, cutoff, observation clocks and official deadline.
Require cutoff ≤ registration time < deadline. A hash without retained forecast
bytes is insufficient. A source snapshot without predictions is not a forecast.
Never reconstruct a missed deadline retrospectively.

Score all eligible official player-fixtures. Record exclusions before outcomes
are joined. Compare candidate and original on the same identities, source
universe and cutoffs. New sources/parameters require a new version and a new
evaluation window. No interim tuning. The first registered origin is selected
before its results; all subsequent consecutive eligible origins are included.

## Minimum evidence and decision

No decision before 12 distinct PL deadlines, 200 matches, 10,000 matched
player-fixtures and 300 observations in each pre-cutoff role group (regular,
rotation, reserve). This is a minimum, not an automatic sufficient power claim.
Report unresolved rare injury/return groups as insufficient evidence.

Use paired chronological four-GW block resampling, 10,000 fixed-seed draws,
within-season blocks, 95% intervals. Publish all club/role estimates, sample
sizes, tail errors and intervals; subgroup estimates are not independent tests.
If intervals are too wide, continue collecting without tuning or moving gates.

Candidate marginal p/q/s/c/x must match frozen B inference within 1e-6 minute
and 1e-6 probability on identical input packs. This is a numerical integration
tolerance, not a prediction-accuracy allowance. Relative to original MM, require
the upper paired 95% bounds for MAE, RMSE and start-Brier deltas to be ≤ 0.
Require no significant increase in >60-minute errors. Any club/role showing
clear harm remains an unresolved gate; do not introduce post-hoc club switches.

Report start log-loss and calibration (fixed deciles), appearance Brier,
starter/cameo duration, all minute tails, exact XI hits and legal formations.
Independently require zero illegal XI assignments and zero minutes for an
applicable verified OUT/SUSPENDED source. Audit contradictions separately.

The experimental PMF needs a separate decision. On matched new observations,
require CRPS and log-loss upper paired delta bounds ≤ 0 versus frozen PR13,
and absolute empirical coverage deviations ≤ 5 percentage points for 50/80/90%
intervals, with uncertainty intervals reported. A nominal interval cannot be
called calibrated solely because discrete contained model mass exceeds nominal.
Mean agreement must stay within 1e-6. Until then the PMF remains experimental.

Passing statistical criteria does not override source-timing, injury, identity,
leakage, reproducibility or other existing certification failures.

## Current collection state

The existing entry point can register supplied valid B feature packs. The
registration clock bug (cutoff confused with deadline) is corrected. Official
public bootstrap/fixture capture is automated separately and explicitly reports
`BLOCKED_CURRENT_B_FEATURES` while no verified current PR8 feature producer
exists. These artifacts preserve source evidence; they do **not** count toward
the sample requirements above. No prospective B accuracy result is claimed.

The 2024/25 and 2025/26 periods and the previously inspected 2026/27 diagnostics
are reused research data, not untouched validation.
