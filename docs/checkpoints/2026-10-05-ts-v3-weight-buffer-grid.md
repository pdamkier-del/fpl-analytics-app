# TS v3: 6GW weights and hit-buffer grid

## Scope and provenance

Started from current branch HEAD `08fc9670f1b6aedfeed1851effdfd0e721db6e91`.
The protocol and runner were published before completed outcomes in
`31206e313ffa282c72a467f84827b1eaf43758f4`.
All 36 requested combinations are full GW1–38 2025/26 replays, not coarse samples.

The five supplied manual weight sequences and seven exponential sequences
`rho**k`, `k=0..5`, rho 0.60 through 0.90 in 0.05 steps, are crossed with
buffers 1.0, 1.5 and 2.0. The existing frozen `run_v3` function is called directly,
with only its WEIGHTS and BUFFER parameters varied. Eight isolated worker
processes schedule replays in parallel. No search code, search limits,
point-model code, forecast data, actual-point engine or price logic is modified.
251 source/input files are hashed before the grid and checked afterward.

Search retains 18 targets per position, local beam 60, 12 returns per depth,
outer beam 20 and 0–5 optional transfers. State includes squad, bank, FT and
purchase prices; FT is capped at 5. Each origin plans a dynamic six-GW path,
optimizes XI/captain by GW and executes only the first action. Chips remain OFF.
The planner has no fixed 2.16-point charge for banked FT. All runs begin with the
same initial squad and share the 1,425-point no-transfer control.

## Temporal protocol

Development selection: maximize actual net points in GW1–21, then break ties
by fewer GW1–21 hit points, fewer GW1–21 transfers and lexicographic label.
The season maximum is explicitly labelled hindsight and is not the selection rule.
Later GW22–38 totals retain the policy's own state from the first period; squads
are not reset at GW22. Tied sets of period optima are reported so a different
arbitrary tie-break is not confused with incompatible temporal optima.

The later period is a temporal diagnostic, not an untouched holdout: this season
and these recovered rolling Phase5Q forecasts have already been examined.
Robustness rankings using both periods are exploratory rather than independent
validation. No vFinal point model is fitted or evaluated by this proxy grid.

## Existing forced-transfer accounting defect

The frozen replay contains a corner case: `legalize_team_limit` makes a mandatory
club-limit repair but does not consume FT before the rolling planner is invoked.
The optional action can therefore reuse that FT. This is an existing defect,
not a change introduced by weight/buffer tuning.

For example, `manual_070_045_buffer_2.0` in GW22 made two transfers (one forced)
with only one available FT and recorded zero hit points; official accounting
requires four. This also affects the decision cost, so subtracting missing hits
from the final score would not recreate a valid strategy replay.

Mechanics are left frozen as explicitly requested. The raw grid, raw averages
and predeclared raw development choice remain intact. An additional audit walks
all GW transfers from FT=0, including forced moves, and checks official hit
points, FT transitions and the five-transfer limit. Invalid combinations are
flagged and analysed separately, not silently corrected or promoted.
The audit was added after observing the defect; its validity filter is reported
separately from the original development selection rule.

Valid-only buffer means can have different weighting counts. A second comparison
uses only weightings whose three buffer runs all pass the audit, to keep the
buffer comparison balanced. Averages by weighting and family are provided both
for the raw grid and for audit-valid results.

## Runtime and outputs

Every run saves parameters, 38-GW metrics, full hypothetical paths and resumable
squad/purchase/bank/FT state. `runtime_seconds` sums weekly planning and scoring
durations; input loading/checkpoint writing are excluded. Invocation wall and CPU
time are also saved. Concurrent runtimes should not be treated as identical to
the earlier isolated baseline measurements. The overall grid wall time is reported
separately from the sum of per-replay runtimes.

All artifacts are in `analysis/results/ts-v3-weight-buffer-grid-20261005-v1/`.
`ranking.csv` contains the full raw ranking, with season/dev/later ranks and
comparisons against TS v3 baseline and TS v2. `ranking_audited.csv` adds accounting
validity; `ranking_valid.csv` supplies ranks within valid results. `temporal_analysis.json`
contains the raw choice, valid development candidate, later optimum, tied maxima
and robustness diagnostics. Exact input/output hashes are in the manifests.

## Completed results and conclusions

All **36/36** full seasons completed in **17m23s** wall time using eight workers.
33 pass the official transfer-accounting audit; three fail the existing mandatory
repair corner case. The point model, TS v3 mechanics/search and all 251 frozen
source/input hashes remained unchanged. Sixteen planner/replay tests passed.
All persisted 38-GW logs, 38 executed actions, totals and complete paths were checked.
A missing persisted GW38 tail in one completed run was recovered with the same
frozen code/parameters, reproducing all score metrics; original measured runtime
was preserved (`tail_recovery.json`).

### Temporal selection, not the full-season maximum

| Strategy / role | GW1–21 | GW22–38 | Season | Transfers | Hit points | Uplift vs no transfers |
|---|---:|---:|---:|---:|---:|---:|
| TS v3 baseline | 1,039 | 953 | 1,992 | 45 | 32 | +567 |
| Development choice: rho 0.90, buffer 1.0 | 1,088 | 866 | 1,954 | 52 | 60 | +529 |
| Valid hindsight maximum / later winner: rho 0.60, buffer 1.0 | 1,046 | 984 | 2,030 | 46 | 36 | +605 |
| TS v2 comparator | 1,160 | 977 | 2,137 | 54 | 68 | +712 |

The predeclared development winner is unique and accounting-valid:
`(1, .90, .81, .729, .6561, .59049)`, buffer 1.0.
It improves development by 49 points but loses 87 points in the later check,
finishing **38 below baseline**. Its later rank is 31st of 33 valid combinations.

The later winner is uniquely rho 0.60 / buffer 1.0:
`(1, .60, .36, .216, .1296, .07776)`. It ranks 9th on development and 1st later.
There is **no overlap between the period-optimal sets**. This is a real temporal
switch, not an arbitrary tie-break. This combination is the only valid one that
strictly improves both baseline periods: **+7 early, +31 later**.
It is an exploratory future-validation candidate, not a replacement chosen by
the predeclared development rule. Default weights and buffer are not changed.

### Answers to the four questions

1. **Harder decay does not help consistently.** Rho 0.60 works best in hindsight,
   but rho 0.65–0.75 and several harder manual sequences perform worse. The early
   optimum actually uses the much softer rho 0.90 and fails the later check.
2. **Buffer 1.5 has the strongest balanced valid average.** Across the same nine
   weightings valid at all three buffers, means are 1,967.89 (1.5), 1,958.33 (2.0)
   and 1,957.11 (1.0). Buffer 1.0 wins the best individual valid combination;
   there is no universally best buffer independent of weighting.
3. **Rho 0.60 / buffer 1.0 improves both periods**, but this is a reused-season
   diagnostic. Rho 0.85 is also relatively insensitive to buffer (2,000–2,010
   season points), with a nearly neutral early period (1 point below baseline)
   and 9–19 more later points. It does not strictly beat baseline in both periods.
4. **Tuning recovers at most 38 of the 145 lost points among valid runs: 26.2%.**
   The remaining gap to TS v2 is **107 points**. The development-selected setting
   recovers none: it loses 38 points versus baseline and 183 versus TS v2.
   This grid does not justify replacing the baseline on the strength of a
   full-season maximum or claiming most of the original gap has been resolved.

The raw maximum is 2,051 points (two tied combinations), but both tied runs fail
FT accounting. Those scores must not be used as evidence of a valid improvement.
The experiment leaves the defect untouched; addressing it would require a
separate mechanics fix and replay, outside this frozen tuning experiment.

### Buffer averages

Raw means include all requested combinations, including flagged runs:

| buffer | count | mean_points | mean_dev | mean_late | mean_transfers | mean_hit_points |
| --- | --- | --- | --- | --- | --- | --- |
| 1.00 | 12.00 | 1952.67 | 1038.50 | 914.17 | 45.58 | 34.33 |
| 1.50 | 12.00 | 1968.42 | 1037.83 | 930.58 | 43.33 | 25.00 |
| 2.00 | 12.00 | 1976.42 | 1043.58 | 932.83 | 42.08 | 19.67 |

Balanced valid-only comparison: same nine weightings per buffer:

| buffer | count | mean_points | mean_dev | mean_late | mean_transfers | mean_hit_points |
| --- | --- | --- | --- | --- | --- | --- |
| 1.00 | 9.00 | 1957.11 | 1037.67 | 919.44 | 45.78 | 35.11 |
| 1.50 | 9.00 | 1967.89 | 1032.78 | 935.11 | 43.67 | 26.67 |
| 2.00 | 9.00 | 1958.33 | 1033.78 | 924.56 | 42.44 | 21.78 |

### Weighting averages

Raw means, all three buffers per weighting:

| name | count | mean_points | mean_dev | mean_late | min_points | max_points |
| --- | --- | --- | --- | --- | --- | --- |
| exp_0.60 | 3 | 2015.00 | 1062.67 | 952.33 | 1990 | 2030 |
| exp_0.65 | 3 | 1948.67 | 1043.33 | 905.33 | 1845 | 2051 |
| exp_0.70 | 3 | 1926.33 | 1027.33 | 899.00 | 1863 | 1958 |
| exp_0.75 | 3 | 1919.67 | 997.00 | 922.67 | 1901 | 1947 |
| exp_0.80 | 3 | 1960.67 | 1041.00 | 919.67 | 1948 | 1971 |
| exp_0.85 | 3 | 2006.00 | 1038.00 | 968.00 | 2000 | 2010 |
| exp_0.90 | 3 | 1958.33 | 1057.33 | 901.00 | 1951 | 1970 |
| manual_070_045 | 3 | 1976.33 | 1061.00 | 915.33 | 1935 | 2051 |
| manual_075_055 | 3 | 1950.67 | 1022.00 | 928.67 | 1924 | 1964 |
| manual_080_060 | 3 | 2010.00 | 1069.00 | 941.00 | 2004 | 2019 |
| manual_085_065 | 3 | 1946.33 | 1022.00 | 924.33 | 1924 | 1964 |
| manual_baseline | 3 | 1972.00 | 1039.00 | 933.00 | 1954 | 1992 |

Valid-only means; counts below three identify an excluded accounting-invalid run:

| name | count | mean_points | mean_dev | mean_late | min_points | max_points |
| --- | --- | --- | --- | --- | --- | --- |
| exp_0.60 | 2 | 2010.00 | 1055.50 | 954.50 | 1990 | 2030 |
| exp_0.65 | 2 | 1897.50 | 1026.50 | 871.00 | 1845 | 1950 |
| exp_0.70 | 3 | 1926.33 | 1027.33 | 899.00 | 1863 | 1958 |
| exp_0.75 | 3 | 1919.67 | 997.00 | 922.67 | 1901 | 1947 |
| exp_0.80 | 3 | 1960.67 | 1041.00 | 919.67 | 1948 | 1971 |
| exp_0.85 | 3 | 2006.00 | 1038.00 | 968.00 | 2000 | 2010 |
| exp_0.90 | 3 | 1958.33 | 1057.33 | 901.00 | 1951 | 1970 |
| manual_070_045 | 2 | 1939.00 | 1053.00 | 886.00 | 1935 | 1943 |
| manual_075_055 | 3 | 1950.67 | 1022.00 | 928.67 | 1924 | 1964 |
| manual_080_060 | 3 | 2010.00 | 1069.00 | 941.00 | 2004 | 2019 |
| manual_085_065 | 3 | 1946.33 | 1022.00 | 924.33 | 1924 | 1964 |
| manual_baseline | 3 | 1972.00 | 1039.00 | 933.00 | 1954 | 1992 |

### Family averages

Raw:

| family | count | mean_points | mean_dev | mean_late | min_points | max_points |
| --- | --- | --- | --- | --- | --- | --- |
| exponential | 21 | 1962.10 | 1038.10 | 924.00 | 1845 | 2051 |
| manual | 15 | 1971.07 | 1042.60 | 928.47 | 1924 | 2051 |

Valid only:

| family | count | mean_points | mean_dev | mean_late | min_points | max_points |
| --- | --- | --- | --- | --- | --- | --- |
| exponential | 19 | 1954.11 | 1034.00 | 920.11 | 1845 | 2030 |
| manual | 14 | 1965.36 | 1040.14 | 925.21 | 1924 | 2019 |

### Full 36-combination raw ranking

False in the final column means the path fails official accounting. Runtime is weekly planning/scoring seconds under concurrent scheduling.

| label | total_points | transfers | hit_points | uplift | points_gw1_21 | points_gw22_38 | runtime_seconds | official_transfer_accounting_valid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| exp_0.65_buffer_2.0 | 2051 | 41 | 12 | 626 | 1077 | 974 | 223.34 | False |
| manual_070_045_buffer_2.0 | 2051 | 41 | 12 | 626 | 1077 | 974 | 225.73 | False |
| exp_0.60_buffer_1.0 | 2030 | 46 | 36 | 605 | 1046 | 984 | 213.85 | True |
| exp_0.60_buffer_1.5 | 2025 | 41 | 12 | 600 | 1077 | 948 | 223.07 | False |
| manual_080_060_buffer_1.0 | 2019 | 46 | 36 | 594 | 1069 | 950 | 205.91 | True |
| exp_0.85_buffer_1.5 | 2010 | 45 | 32 | 585 | 1038 | 972 | 188.56 | True |
| exp_0.85_buffer_1.0 | 2008 | 46 | 36 | 583 | 1038 | 970 | 185.30 | True |
| manual_080_060_buffer_1.5 | 2007 | 44 | 28 | 582 | 1069 | 938 | 211.51 | True |
| manual_080_060_buffer_2.0 | 2004 | 43 | 24 | 579 | 1069 | 935 | 225.54 | True |
| exp_0.85_buffer_2.0 | 2000 | 43 | 24 | 575 | 1038 | 962 | 190.04 | True |
| manual_baseline_buffer_1.5 | 1992 | 45 | 32 | 567 | 1039 | 953 | 200.65 | True |
| exp_0.60_buffer_2.0 | 1990 | 41 | 16 | 565 | 1065 | 925 | 240.07 | True |
| exp_0.80_buffer_1.0 | 1971 | 47 | 40 | 546 | 1038 | 933 | 194.95 | True |
| exp_0.90_buffer_1.5 | 1970 | 44 | 28 | 545 | 1042 | 928 | 183.41 | True |
| manual_baseline_buffer_1.0 | 1970 | 46 | 36 | 545 | 1039 | 931 | 196.25 | True |
| manual_075_055_buffer_1.5 | 1964 | 42 | 20 | 539 | 1022 | 942 | 215.31 | True |
| manual_075_055_buffer_1.0 | 1964 | 43 | 24 | 539 | 1022 | 942 | 204.31 | True |
| manual_085_065_buffer_1.0 | 1964 | 43 | 24 | 539 | 1022 | 942 | 195.20 | True |
| exp_0.80_buffer_2.0 | 1963 | 44 | 28 | 538 | 1047 | 916 | 204.64 | True |
| exp_0.70_buffer_1.5 | 1958 | 42 | 20 | 533 | 1029 | 929 | 220.36 | True |
| exp_0.70_buffer_2.0 | 1958 | 42 | 20 | 533 | 1029 | 929 | 225.96 | True |
| manual_baseline_buffer_2.0 | 1954 | 42 | 20 | 529 | 1039 | 915 | 208.85 | True |
| exp_0.90_buffer_1.0 | 1954 | 52 | 60 | 529 | 1088 | 866 | 169.66 | True |
| exp_0.90_buffer_2.0 | 1951 | 43 | 24 | 526 | 1042 | 909 | 187.86 | True |
| manual_085_065_buffer_1.5 | 1951 | 45 | 32 | 526 | 1022 | 929 | 213.22 | True |
| exp_0.65_buffer_1.5 | 1950 | 44 | 28 | 525 | 1029 | 921 | 227.90 | True |
| exp_0.80_buffer_1.5 | 1948 | 43 | 24 | 523 | 1038 | 910 | 202.44 | True |
| exp_0.75_buffer_2.0 | 1947 | 41 | 16 | 522 | 996 | 951 | 206.95 | True |
| manual_070_045_buffer_1.0 | 1943 | 44 | 28 | 518 | 1053 | 890 | 222.58 | True |
| manual_070_045_buffer_1.5 | 1935 | 42 | 20 | 510 | 1053 | 882 | 223.56 | True |
| manual_075_055_buffer_2.0 | 1924 | 42 | 20 | 499 | 1022 | 902 | 223.17 | True |
| manual_085_065_buffer_2.0 | 1924 | 42 | 20 | 499 | 1022 | 902 | 213.84 | True |
| exp_0.75_buffer_1.5 | 1911 | 43 | 24 | 486 | 996 | 915 | 204.97 | True |
| exp_0.75_buffer_1.0 | 1901 | 45 | 32 | 476 | 999 | 902 | 204.62 | True |
| exp_0.70_buffer_1.0 | 1863 | 44 | 28 | 438 | 1024 | 839 | 231.18 | True |
| exp_0.65_buffer_1.0 | 1845 | 45 | 32 | 420 | 1024 | 821 | 239.48 | True |

### Accounting violations

| label | gw | total_transfers | legal_ft_before | expected_hit_points | recorded_hit_points |
| --- | --- | --- | --- | --- | --- |
| exp_0.65_buffer_2.0 | 22 | 2 | 1 | 4 | 0 |
| manual_070_045_buffer_2.0 | 22 | 2 | 1 | 4 | 0 |
| exp_0.60_buffer_1.5 | 22 | 2 | 1 | 4 | 0 |

## Archive and reproduction

Top-level summaries and each combination's `result.json` and 38-GW log are
published directly. `full_replay_artifacts.zip` contains all per-combination
parameters, logs, paths and final resumable checkpoints. Extract it into the grid
output directory before inspecting archived paths or resuming a partial run.
The manifest lists both directly published files and every archive member hash.

Run with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src
python scripts/run_ts_v3_weight_buffer_grid.py --workers 8` (as one shell command).
The analysis is reproducible with `python scripts/analyze_ts_v3_weight_buffer_grid.py`.
Source and parameter mismatches are rejected. No Git HTTPS push or credentials
are used for publication; commits use the authenticated GitHub Git Data API.
