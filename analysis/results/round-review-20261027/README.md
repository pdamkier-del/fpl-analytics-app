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

## Outstanding private transfer comparison

The existing best-XI-from-15 and no-budget league-XI benchmarks are not the requested best legal transfer move. Historical bank, free transfers, transaction/selling prices and chip state are incomplete in the screenshot archive. No feasible transfer optimum is claimed or fabricated. The UI explains the prerequisite explicitly. The normal predeadline TS remains unchanged. There is no new retrospective transfer solver in this change.

## Validation

- Full Python suite: 1084 passed.
- `node tests/test_round_review.js`: series/missing-data/signed errors/repeat signal and chronological cutoff checks.
- `node tests/test_season_team_comparison.js`: existing lineup, captain, autosubs, hits, chips and archive checks.
- Desktop/mobile browser: new round/profile report, retained backtest, player match card and private season comparisons.
- Private screenshot import exercised locally only; public browser uses synthetic/empty personal data.

Public release evidence is recorded after the deployment completes. Production assets and the latest live numerical artifacts must retain their hashes.
