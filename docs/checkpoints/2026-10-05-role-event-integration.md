# Completed role-event paired simulation; website deferred

Implemented opt-in soft 21-role priors for goals, assists and DefCon with
individual history, shrinkage and exact broad-position fallback. FPL scoring
positions unchanged. Development GW16–21 selected 900-minute shrinkage for
all three events before evaluation. Conditional Poisson deviance improved
3.1%, 2.4%, 9.8% respectively. Actual exposure minutes were used for those
conditional rate tests; these are not forecast-point improvements.

All 26,159 role states independently reconstructed; 3,121/3,168 actual
starters have known roles. Inherited availability convention is kickoff+3h,
not authoritative publication timestamps. GW1–5 contributes broad priors
but lacks historical soft-role pooling.

## Simulation

144 fixtures / 11,794 player-fixture rows, GW22–38 reused diagnostic.
NOT a full new-model season, NOT a new holdout; same 26 fixtures excluded.
Current v4 minutes vs identical v4 minutes plus role event priors. Original
simulator, frozen adapter and transfer/chip policies unchanged.

Fixed finalist: 3 predetermined seeds x 400 draws = 1,200 per fixture/arm.
Average forecasts across seeds before scoring nonbonus points:

| Metric | Current v4 | v4 + roles |
|---|---:|---:|
| MAE | 0.828379 | 0.829757 |
| RMSE | 1.576204 | 1.578294 |
| Bias | +0.044715 | +0.044258 |

Role MAE slightly worse in every seed. No demonstrated total-point gain;
not proof of statistically established inferiority. No promotion.

## Component diagnosis (80 draws only)

Higher-precision run retains total forecasts only. Component results use
saved 80-draw forecasts and reconstructed Core point components, not an
official component ledger. Components sum to observed total on all rows.
Means below use relevant position cohorts; raw MAEs across components are
not comparable. Sparse outcomes/DNP rows can hide individual weaknesses.

| Component | Current-v4 predicted mean | Actual mean | Diagnosis |
|---|---:|---:|---|
| Appearance | 0.6069 | 0.6188 | Slightly low; substitute duration weak |
| Goals | 0.1663 | 0.1517 | 9.6% high; roles slightly improve component error |
| Assists | 0.0963 | 0.0903 | 6.6% high; roles slightly improve component error |
| Clean sheets | 0.1831 | 0.1791 | Aggregate close (+2.2%), not individual calibration |
| Saves, GK | 0.1080 | 0.1315 | 17.9% low |
| DefCon, outfield | 0.1197 | 0.0976 | 22.7% high; roles slightly improve component error |
| Cards/own-goal penalties | -0.0380 | -0.0545 | Penalty magnitude 30.3% too small |
| Goals-conceded penalties | -0.1207 | -0.1188 | Aggregate close |
| Bonus | 0.0917 | 0.0779 | Invalid season comparison: inherited wrong-season BPS |

Penalty saves/misses are absent from simulator component mapping. Small
changes in unchanged components can arise from simulator randomness.
Role priors alone cannot repair team totals, keeper saves or bonus rules.

Earlier original-v2 vs v4 minute comparison (different comparator): MAE
11.9697 -> 11.5093 (-3.85%); start Brier 0.07775 -> 0.07578. Main gain DNP.
Actual substitutes worsen 19.4127 -> 20.6401 minutes MAE; forwards weaker.

## Verification and next gate

131 tests passed in canonical tests/ suite; 218 experiment integrity checks
pass. Saved 80-draw v4 reproduces exactly. Packed outputs/source checksums,
fallback, unchanged fields, conserved team means and policy hashes verified.
Scripts: check_role_event_experiment.py and summarize_role_simulation.py.

Full new-model season blocked by 196 origin-target cells, 32 roster rows in
26 fixtures, early as-of/competition coverage and season-rule integration.
Old-model 2,096 net season points are unrelated to this candidate.
Retain current v4; no tuning on GW22–38. Future changes need development-only
selection and independent evaluation. Website explicitly deferred by user;
tracked website restored exactly, unpublished drafts under ignored
work/website-deferred-20261005/. Nothing activated or published to website.
