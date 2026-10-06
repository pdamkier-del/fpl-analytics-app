# MM v2 with original external ratings — final captured experiment

Only MM ingestion, audits and descriptive diagnostics were added. Existing MM mathematics, durations, PM and TS remain unchanged. GW22–38 is reused diagnostic data, not independent OOS.

## Result

| Model | MAE | RMSE | State log-loss | State Brier |
|---|---:|---:|---:|---:|
| locked_MM | 11.487502 | 21.437602 | 0.435694 | 0.231781 |
| XI_only | 11.477555 | 21.432928 | 0.435573 | 0.231784 |
| XI_external_ratings | 11.487502 | 21.437602 | 0.435694 | 0.231781 |

There are 13,987 identical reused prediction rows. The original development rule selected no ratings candidate (`selected_l2=null`). All four rating candidates worsened development state log-loss by approximately 0.000431–0.000461. Development MAE improved by 0.0306–0.0552 minutes, while RMSE worsened by 0.0391–0.0411 minutes. The existing requirement of an improved state log-loss was not satisfied. The unchanged experiment therefore returns the locked MM probabilities and minutes; the zeros in the final test deltas are the selection fallback, not evidence that rating features are numerically inert.

No ratings candidate is promoted. No new parameter or slice threshold was tuned to GW22–38. XI-only retains its previously reported small reused-data improvement but this does not make the rejected ratings candidate an improvement.

## Descriptive cases

- uncertain_starter: 2,644 rows; locked/fallback MAE 29.912823, RMSE 34.683745.
- multi_role: 2,365 rows; locked/fallback MAE 21.510837, RMSE 29.671083.
- close_role_competition: 332 rows; locked/fallback MAE 25.399652, RMSE 31.651424.
- observed_lineup_shock: 521 rows; locked/fallback MAE 69.257766, RMSE 70.935590.
- bad_form_incumbent_replacement: 94 rows; locked/fallback MAE 61.025936, RMSE 65.557163.

There are 47 descriptive incumbent/competitor pairs involving 94 distinct prediction rows. Examples include Reijnders/Foden (GW22), Rutter/Gruda (GW22), Castagne/Tete (GW26) and Mings/Torres (GW37). These identify an actual incumbent nonstart and higher prior recent rating for a starting competitor in the same expected role. They do not establish that the coach made the selection because of ratings. Since development rejected the residual, the final ratings probabilities do not improve the 521 lineup-shock rows or these 94 case rows. The full pair file retains exact player UUIDs, prior ratings/trends, forecast probabilities and actual minutes.

`descriptive_slices.csv` includes state/start log-loss/Brier and minute errors for every GW, club and fine role, plus uncertainty, multi-role, close competition and up/down trends. Requested GWs 30,22,31,36,32,38,37,29 are all present. `auditable_diagnostic_predictions.csv.gz` also retains cutoffs, q/H, unchanged conditional bench appearance and duration expectations, original rating features and all three model predictions.

## Data and coverage

Valid requested-season provider rows: 15,784; mapped: 14,522; unresolved: 1,262; ambiguous: 0. Provider: FotMob, original 0–10 values. SofaScore official API returned HTTP403. No synthetic provider rows, normalisation or fuzzy player matching were used.

| 2025/26 competition | Original rated matches | Matches with mapped ratings |
|---|---:|---:|
| prem | 380 | 380 |
| champions-league | 69 | 48 |
| europa-league | 29 | 16 |
| conference-league | 17 | 5 |
| fa-cup | 43 | 43 |
| efl-cup | 38 | 37 |

Original ratings were fetched for every eligible completed match returned by the 2025/26 inventories. Internal match-ID coverage is incomplete in Europe: quarantined date-free/repeated fixtures and absent certified internal IDs stay unresolved, and their original provider facts remain in the raw ledger. Counting a match as mapped means at least one mapped rated player; it does not claim every player was resolved. Per-team games and per-row identity counts are separately audited.

All 20 corresponding PL clubs were mapped by permanent club code in each season. 2026/27 expansion includes the available original PL, Europe and EFL ratings, but the latest returned rated kickoff is 2026-09-20. It must not be described as verified complete through October 6. The provider's 2026/27 FA query fell back to old January–May 2026 fixtures. July-to-June season guards now reject such fallback data. 41 old fixture rows / 767 unmapped player rows were removed from future-season coverage and retained in `rejected_previous_season_rows.csv.gz` for audit. None was a model input; the mapped rating-ledger SHA256 before and after is identical, so the captured experiment remains valid without another model fit. Genuine 2026/27 FA Cup ratings are not established here.

Duplicate provider/player/match, out-of-range ratings and target-match leakage are all zero under the documented availability proxy. `available_at = kickoff + 6 hours` for provider-confirmed completed matches is a conservative proxy, not an observed historical publication timestamp. Later provider revisions cannot be certified. The coverage audit records both limitations explicitly.

## Reproduction and lineage

The successful GitHub run is https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/37480129973 at collector commit `07ca4e8594f991597868d13a186d50a488e39fc5`. Its unchanged experiment, exact mapping tests, offline ledger rebuild and companion slice analysis all succeeded. Postcapture season-scope cleanup affected only unmapped raw/audit rows. The offline ledger rebuild was rerun against the final data and matches all 14,522 model-input rows. The eight ingestion tests include phase/parent competition validation, conflicting provider anchors, unfinished matches and previous-season fallback rejection. The published data manifest carries SHA256 checksums of all required ledger-rebuild inputs.

Run commands and source pins are documented in `docs/checkpoints/2026-10-06-mm-external-rating-reproduction.md`. The model input hash is:

bc113a5805a60ee4dd6e68238d0edcd223aefd477429ac6339ba71fcb27ab861
