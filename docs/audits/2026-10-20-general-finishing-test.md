# General test of finishing and on-pitch receiver conversion

The new isolated replay is complete: **501 fixtures, 39,264 player/fixture forecasts per arm, four arms and 801,600 complete match simulations**. All 733 Python regressions passed. Every original 400-draw player xP reproduces the archived reference exactly, and the original aggregate MAE/RMSE/bias reproduce the previously verified historical reports.

**Decision: keep the deployed PM unchanged.** Individual finishing gives small MAE and RMSE gains in both periods, but the paired MAE intervals include zero. Receiver-weighted conversion gives small assist log-loss gains in both periods, with intervals also including zero, and does not improve overall xP MAE. The mechanism remains plausible; these results neither establish a deployment-ready improvement nor demonstrate that finishing is irrelevant.

## What this new experiment isolates

The earlier player-PM-v2 experiment also refitted player profiles and context. This experiment changes only finishing allocation and/or minute-by-minute receiver conversion on the original inputs. MM parameters, team-strength forecasts, xG/xA weights, original scoring/BPS/bonus and the penalty process remain unchanged. The selected historical conversion setting is reused rather than tuned to these outcomes or named players.

Protocol: `analysis/results/general-conversion-20261020/protocol.md`, written before the new replay. The archive contains 171 relevant 2024/25 fixtures and 330 in 2025/26; the initial planning count of 170 for 2024 was corrected on inventory, without exclusions based on outcomes.

A player's conversion factor is `(past goals + 20)/(past xG + 20)`, using all available history before the forecast cutoff. Unknown players are neutral. Known early-2022/23 expected-stat placeholders are excluded. No target xG, minutes, goals or assists are forecast inputs. These are all-xG calibration factors, including penalties, not identified non-penalty finishing skill.

At each sampled minute, let `g_i` be original active scorer weight, `theta_i` the finishing factor and `L` the original ordinary-goal intensity after the unchanged penalty budget:

- **Original:** intensity `L`, scorer share `g_i/sum(g)`.
- **Individual:** intensity `L`, scorer share `g_i*theta_i/sum(g*theta)`.
- **Receivers:** intensity `L*sum(g*theta)/sum(g)`, original scorer shares.
- **Combined:** adjusted intensity and adjusted scorer shares. Individual intensity is therefore `L*g_i*theta_i/sum(g)`: conversion is applied once.

A generated ordinary goal then uses the original assist probability and chooses an active teammate excluding the scorer. Consequently receivers affect assists through actual goal conversion; no assist is independently added to an old point forecast. Full opponents, clean sheets and BPS/bonus are resimulated. Bench players contribute only while on the pitch. If active scorer weight is absent, the multiplier is neutral, preserving original behavior rather than introducing a separate physics correction.

The receiver-only arm is a mechanism ablation affecting joint goal/assist output, not an artificial change to assists while holding scored goals fixed. It uses goal weights as chance-share proxies; it is not a learned creator→receiver network. xA observations are unchanged.

## Historical results

Evaluation windows: 2024/25 GW22–38 and 2025/26 GW6–38. These are reused historical research periods, not pristine independent holdouts. Lower errors/log losses are better. Point MAE is across all forecast roster rows; played-player metrics are retained separately.

| Model | 2024/25 xP MAE | 2025/26 xP MAE | 2024/25 xP RMSE | 2025/26 xP RMSE |
| --- | ---: | ---: | ---: | ---: |
| Original | 0.947794 | 0.929173 | 1.848146 | 1.880707 |
| Individual | 0.947330 | 0.928975 | 1.847881 | 1.880240 |
| Receivers | 0.950157 | 0.929322 | 1.851183 | 1.879787 |
| Combined | 0.949364 | 0.929275 | 1.850419 | 1.879572 |

Individual MAE improves by about **0.049% / 0.021%**, not a large correction. Fixture-paired 95% intervals for the absolute MAE change are `[-0.001068, +0.000127]` and `[-0.000652, +0.000271]`. Both include zero. Receiver-only MAE deltas are `+0.002363` and `+0.000149`; combined deltas are `+0.001570` and `+0.000102`. Their intervals also include zero.

| Model | 2024/25 goal log loss | 2025/26 goal log loss | 2024/25 assist log loss | 2025/26 assist log loss |
| --- | ---: | ---: | ---: | ---: |
| Original | 0.108120 | 0.099761 | 0.110705 | 0.108456 |
| Individual | 0.108126 | 0.099735 | 0.110688 | 0.108457 |
| Receivers | 0.108122 | 0.099826 | 0.110487 | 0.108288 |
| Combined | 0.107926 | 0.099706 | 0.110561 | 0.108311 |

Receiver-only assist log-loss changes are `-0.000218 / -0.000168`, with paired intervals `[-0.001139,+0.000808]` and `[-0.000899,+0.000524]`. Combined improves both goal and assist log loss in both periods, but neither the observed small gains nor the point regression are precisely established. Do not describe these as proven general improvements.

All reports include bias, Brier scores, bonus error, calibration bins, played-player/position groups and pre-match finishing/history cohorts. Individual adjustment improves point MAE among factors below 0.95 and worsens it above 1.05 in both periods. That does not prove an asymmetric skill rule: MAE favors conditional medians rather than means, and proper event-score patterns differ. No new cap or one-sided adjustment was selected from these outcomes.

## Limits and next decision boundary

- The current source does not identify compatible multi-season non-penalty finishing or observed creator→shot links for unsuccessful chances. This is a general effective-conversion test using available inputs.
- Historical source clocks inherit kickoff+3/4h proxies. Temporal masking is enforced but does not invent actual publication clocks.
- Independent original minute sampling is held as the same law in all arms; changed events alter RNG paths. Same seeds do not give identical minute realizations across arms. Fixture bootstrap omits some Monte Carlo uncertainty. Binary events use Jeffreys smoothing; count-Poisson scores are approximations.
- No player-specific tuning, penalty-role repair, B-MM/joint-GK interaction test, full six-GW TS improvement, independent new season or production certification is claimed.

The individual factor is the simplest candidate for future higher-precision independent validation. Receiver conversion is a coherent research mechanism with a weak positive assist signal, not a proven point upgrade. Neither is enabled in the public B preview or production from these results. The previously identified current penalty-role discrepancy remains separate.

## Code and evidence

- `src/fpl_v1_1_model/experimental_receiver_conversion.py`: opt-in sampled-lineup conversion via the existing offline intensity adapter. No production module is edited or imports it.
- `scripts/replay_general_conversion.py`: cutoff-safe original reproduction, four-arm replay, cached atomic public captures, full scoring and paired evaluation.
- `scripts/report_general_conversion.py`: completion/reference guards, compact metrics and file hashes.
- `tests/test_experimental_receiver_conversion.py`: five tests for actual availability, chance weighting, no double conversion, unchanged penalties, neutral identity and context restoration.
- `analysis/results/general-conversion-20261020/`: protocol, two complete numerical reports, compact summary and hashed prepared inputs/predictions. Per-fixture scratch caches are not versioned. All data is historical public player/match data; no private manager state is used.

Reproduction with the archived original inputs from Actions run 38565961308 and its `mm-component-inputs-and-results` feature cutoffs:

```bash
PYTHONPATH=src:scripts:. python scripts/locked_numerical_runtime.py scripts/replay_general_conversion.py \
  --original-root /tmp/fpl-general-conversion/original \
  --mm-root /tmp/fpl-general-conversion/mm/mm-research-20261014 --workers 4
python scripts/report_general_conversion.py
```

The committed prepared captures also retain the exact reference input, seed, historical factors and cutoff for every evaluated fixture. The committed prediction tables retain actual outcomes for independent metric checks. Numerical fingerprint hashes are in the seasonal reports; summary hashes bind both tables and prepared captures. App, original simulator, model and private-service files were checked unchanged.
