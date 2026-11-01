# Cherki: published GW8 point and minute diagnostic

Read-only investigation, 22 October 2026. Numerical B and production are unchanged. Evidence and full reconciled point components: `analysis/results/cherki-pm-diagnostic-20261022/diagnostic.json`.

The served public `mm-preview/current/forecast.json` and `mm.json` were downloaded and compared with retained original snapshots of the same player (FPL 399, stable code 466052), same GW8 fixture `live-2026-27-fpl-72`, kicking off 24 October 11:30 UTC. These are observational snapshots, not a fixed-input causal experiment.

| Snapshot (UTC) | P(start) | Analytic xM = PM E[min] | xP |
| --- | ---: | ---: | ---: |
| 20 October 14:33, before CL | 41.27% | 39.87 | 1.9875 |
| 21 October 09:15 | 46.19% | 44.94 | 2.5350 |
| 21 October 21:02 | 46.42% | 45.75 | 2.6300 |
| Served: 22 October 07:48 | 46.54% | 45.63 | 3.0025 |

There is no post-CL decrease across these available snapshots. This does not identify which older version or GW the user may have seen. Different opponent/GW comparisons do not measure a change in the player's skill.

The current low aggregate forecast is consistent with uncertain appearance: normal role is `rotation_or_short_history`, currently AVAILABLE, P(start) 46.54%, conditional starter minutes 88.81, P(cameo | bench) 41.34%, conditional cameo minutes 19.45. The exact minute identity is `0.4654085987 * 88.81178852 + (1 - 0.4654085987) * 0.4134271803 * 19.44780063 = 45.63201823`. The 400-draw sample minute mean is 47.91; it is not the analytic expectation and is not evidence of an MM/PM contract mismatch.

Current point components sum exactly to 3.0025: appearance 1.2, goals .6625, assists .7275, clean sheet .115, defensive contributions .035, bonus .3325, negative events -.07. Across the 160 current samples where Cherki plays 90 minutes, mean points are 5.95. That conditional diagnostic illustrates appearance risk; it is **not** a separately simulated guaranteed-90 prediction or a proposed replacement xP. Current xP Monte Carlo standard error is about .190 points; numerical sampling variation is not model predictive uncertainty.

## Implementation trace

- `scripts/build_current_b_inputs.py::current_observations` and `scripts/current_b_features.py::prior_features`: B role/NUM histories and explicit 7/14-day workload use verified PL observations. A confirmed unused PL substitute is available nonstarter role evidence. No latent cause/rest inference separates tactical rotation from loss of league role. Existing upstream components have other competition-aware channels, so it would be inaccurate to describe all of MM or PM as PL-only.
- `scripts/pr4_individual_mm.py::role_features`: weighted starts and verified nonstarts feed a shrunk role probability. Identifying the exact causal impact of the Ipswich benching requires removing/reweighting that observation and replaying the complete fitted and team-normalized model; that experiment has not been run here.
- `src/fpl_v1_1_model/deadline_components.py`: baseline goal/assist rates consume PL history with shrunk position/tactical-role priors. A 0-minute observation is not treated as a 90-minute failure; match-index decay may still age past evidence.
- `scripts/build_locked_live_performance_features.py`: separate provider performance ledger consumes player events without a PL-only competition filter, excludes 0-minute appearances, and respects cutoff. `scripts/vfinal_replay_components.py` uses those recent features in soft goal/assist allocation; `scripts/run_soft_role_performance_allocation.py::apply_model` includes minute exposure and normalizes shares within a team. Therefore CL performance can already affect PM through this channel. Exact ingestion of match 6106257 in the served numerical run cannot be certified from the public forecast alone; its original event ledger is not included there.
- `scripts/run_joint_gk_preview.py` attaches B minutes and the unified sampler preserves analytic MM/PM expectation. No numerical issue was demonstrated by this investigation.

## Verified context and remaining question

Source-labelled independent match context confirms unused PL substitute versus Ipswich (17 October), then CL start/90 minutes/one goal versus AEK (20 October), xG .34, xA .42. Club bench source: https://www.mancity.com/news/mens/man-city-ipswich-premier-league-team-news-october-2026-63927837 . Match statistics: https://www.fotmob.com/api/data/matchDetails?matchId=6106257 . Captures and timestamps are recorded in the preceding midweek context audit. The later CL start may inform the current posterior interpretation of the earlier PL omission; it must never enter a forecast issued before that CL match.

The independent context display release kept numerical forecasts byte-identical. The concrete gap is an explicit general, probabilistic rotation explanation that can preserve the latent role while separately accounting for CL fatigue. This investigation does not establish that 46.54% is too low or justify a player-specific boost. Historical validation and a frozen-input intervention are needed before changing it.

Validation: 36 targeted tests passed in 6.14 seconds (`test_current_b_features`, `test_deadline_components`, `test_unified_b_chain`, `test_player_match_context`). Diagnostic assertions reconcile point sums, 400-draw sample means, identical fixture identity, MM/PM analytic means, and the minute mixture identity across retained snapshots. No model changes, deployment or production changes were performed.
