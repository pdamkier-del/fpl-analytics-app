# Paired diagnostic completed; full replay blocked by frozen input gaps

Continues `26eb8a7266d39be188b98e28df42d63ba525917e` after exact source recovery
and common-input publication. Original adapter/simulator and transfer/chip
policy are unchanged. v4 replaces only minutes inputs; underlying event rates
and roster are common to both arms.

**103 tests pass.** Original checkpoint integrity still passes all 1,075
manifest checks. The new joint checker passes 99 checks over recovered source
bytes, immutable control/v4 files and complete packed input/output streams.

## Results on the complete-fixture cohort

137 fixtures, 11,226 player-fixture rows; GW22–38 **reused diagnostic**.
The original 80-simulation budget is used in each fixture/arm. Same fixture
seed; random branches can diverge, so this is not event-aligned CRN sampling.
Targets are loaded only after forecasts have been saved. No refit, tuning,
selection or transfer/chip optimization is performed.

| Point reference | Arm | MAE | RMSE | Bias |
|---|---|---:|---:|---:|
| Without bonus (primary sensitivity) | Unchanged V2 control | 0.847208 | 1.587086 | 0.051829 |
| Without bonus (primary sensitivity) | v4 selected minutes | 0.829294 | 1.579785 | 0.038740 |
| Full points, inherited 2026/27 BPS on 2025/26 | Control | 0.956819 | 1.861600 | 0.065063 |
| Full points, inherited 2026/27 BPS on 2025/26 | v4 | 0.938138 | 1.854528 | 0.052199 |

Nonbonus MAE difference is −0.017915 and RMSE difference −0.007301 points.
These small changes do not establish a robust xP improvement with this reused
cohort and low Monte Carlo budget. They do demonstrate executable pairing.
This full-roster population is different from older active-player/GW tables;
do not compare their metric levels. No new blind holdout result is claimed.

Scoring remains an inherited approximation: wrong historical BPS season,
missing BPS background/subtypes, aggregate assist attribution, independent
appearance sampling and clipped normal duration draws. Expected sampled
minutes need not exactly match the analytic input means. Both arms retain the
same mechanics; none of these limitations was fixed mid-comparison.

## Concrete stopping condition

Frozen attack/assist/discipline forecasts are missing for **46** player-fixture
rows; the same 40 non-GK rows also lack DC. Their **33** fixtures were excluded
in both arms. Filling them with zero or running a partial team would change
the event allocation. A complete-roster replay therefore remains blocked.

The simulator imports, original adapter and paired runner are technically
operational, but the full period/season has not passed replay preflight.
The season-rules audit separately flags 2025/26 BPS differences and the
missing GW16 AFCON transfer-balance top-up in the archived orchestration.
No full season replay or app activation was started.

Next continuation: recover/generate the 46 missing component forecasts from
declared frozen parameters and cutoff-safe first-appearance/registration
inputs; verify a full common roster and deadline horizon. Resolve scoring and
season orchestration in separate paired checkpoints with transfer/chip strategy
held fixed. Complete cup/competition-state coverage and a fresh validation
period remain requirements for promotion, beyond technical simulator recovery.

Read `analysis/results/joint-paired-diagnostic-v1/manifest.json` for full
metrics, provenance and prediction-part checksums, and `readiness.json` for the
exact blocking status. Reproduction commands are in the paired-input checkpoint.
