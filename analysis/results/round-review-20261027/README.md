# Per-player and round review from GW6

Presentation only. Numerical model source remains `03d5c4d4777b44bc1d37884a1cf4dde106b45cab`.

- Click any GW in the archived or reconstructed series for player errors.
- Round report shows signed bias, MAE, largest point errors and largest minute errors.
- Repeat signals require at least three final GWs with at least three signed point misses ≥2, or absolute minute misses ≥30. Only observations through the selected GW count. These are investigation thresholds, not significance tests or automatic model corrections.
- Separate original, prospective B and retrospective B series. Missing/provisional results never become zero. All registered players remain included, including nonplayers.
- Player cards lazily load archived season estimates, actuals, signed point/minute errors and archived start chances. No invented historical goal/assist decomposition, injury or trainer explanations.
- Private imports accept the previously retained user screenshots, explicitly labelled as non-API-verified, alongside official exports/backups. A post-event vice captain on the bench is valid; it must not be counted as a twelfth starting player.
- Own displayed-XI xP is a conditional sum of archived player xP + captain bonus − hits. It does not estimate uncertain autosubs and is not asserted to be the original predeadline lineup. BB totals are withheld. Imported actual manager points remain distinct.
- Actual input state and predeadline plan archives are preserved; no private data is committed or published.

## Private historical transfer comparison

`historical_manager_review.py` reconstructs ownership/purchase prices, bank, FT and used chips from an official entry export, complete transfer ledger and checksum-verified initial price snapshot. Every actual transfer count, cash balance, owned squad and hit cost must reconcile with official history. State before GW(x)'s transfers is copied before applying those transfers. No current manager state is modified.

The replay can optionally export its original aligned PM draws. It must run through `locked_numerical_runtime.py`; every numerical forecast row and input checksum must equal the already frozen retrospective series. A replay from a different numerical runtime is rejected, not silently mixed with those old forecasts.

- Own xP uses the same PM samples with legal autosubs and captain/vice fallback. Original nominations are reconstructed by reversing documented FPL autosubs; actual rescoring must equal official net points.
- Model move: existing TS search/settings and shared PM scorer, restricted to the single target GW. Original five-transfer search limit and uncertainty buffer remain. Heuristic best found, not a global stochastic optimum; not an original saved predeadline recommendation.
- Hindsight: all selectable historical roster players, 15-player budget, historical sale values, maximum three per club, legal XI/captain, official hit costs and any number of paid transfers. A MILP global bound is certified only if full legal FPL rescoring attains it. A second optimization minimizes transfers among equal net scores.
- Ordinary transfers and each available chip are shown separately. Used chips in the same half-season are excluded. WC/FH remove hits, BB scores all 15, TC adds a second captain bonus. These are one-GW hindsight alternatives with no future value for chips, bank or FT, not chip-use advice.
- Scope: current verified GW6–8, no double-GW draw aggregation or historical WC/FH ownership reconstruction yet. Those cases fail explicitly. The existing six-GW live strategy is unchanged.
- The complete personal result is a local-only import JSON. Its candidate points are rechecked in the browser against final public match data before display. No entry ID, holdings, purchase prices or private analysis file is published.

Run with `--folder PRIVATE_EXPORT_FOLDER --capsules REPLAY_FOLDER --history-source VERIFIED_HISTORY/match-results.json --markets RETAINED_CAPSULES --out PRIVATE_IMPORT.json`, through `locked_numerical_runtime.py`. Initial snapshot and API records are required; no guessed prices.

## Validation

- Final full Python suite: 1090 passed in 57.04 seconds. Six new tests cover cash/FT reconstruction, budget/sale values, unselectable players, hit costs, chip scoring and historical draw/model identity contracts.
- `node tests/test_round_review.js`: series/missing-data/signed errors/repeat signal and chronological cutoff checks.
- `node tests/test_season_team_comparison.js`: existing lineup, captain, autosubs, hits, chips and archive checks.
- Desktop/mobile browser: new round/profile report, retained backtest, player match card and private season comparisons.
- Private screenshot import exercised locally only; public browser uses synthetic/empty personal data.

Public release evidence is recorded after the deployment completes. Production assets and the latest live numerical artifacts must retain their hashes.

## Published verification

- Reviewed UI: `0bdd51eeb2dd895ac2b0bfa8499b26bd0f4d91a1`.
- CI validation [40583605703](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/40583605703): 1090 Python tests in 72.98 seconds and every UI/browser gate passed; only the final Pages OIDC request failed with HTTP 503/timeout.
- Deployment recovery [40586050331](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/40586050331): success. It reused the exact verified artifact, checked successful prior gates, retained the same UI/mathematical pins, and republished through the existing production-preserving publisher. No model recomputation or test bypass.
- Public Chromium on desktop/mobile: real private-history import, round/profile drilldown and legal transfer benchmark display passed. Private inputs/results were never uploaded; browser proof contains only nonpersonal booleans. Standard TLS verification.
- All three numerical B files byte-identical. All 88 production assets match the production artifact retained for this publication. Compare to that exact artifact, not an older preview receipt predating ordinary production refreshes.
- Final personal import file remains outside the repository under `/workspace/private-fpl-history/`. It must be imported once in the user's own browser; the agent's verification browser does not write the user's localStorage.
