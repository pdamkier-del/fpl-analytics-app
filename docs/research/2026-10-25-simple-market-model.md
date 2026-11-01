# Simpler MM/PM and market input: first fixed screen

Research only; existing B app and production are unchanged. Full protocol and row-level evidence: `analysis/results/simple-market-model-20261025/`.

Five fixed arms were compared on the same **341 fixtures / 27,092 player-fixture observations**, across 2024/25 and 2025/26 GW22–38. No player-specific adjustments or post-score parameter search. These are reused historical research periods, not an independent holdout.

| Mean absolute xP error, points/player-fixture | 2024/25 | 2025/26 |
|---|---:|---:|
| Current selected B | 0.889075 | 0.870893 |
| Analytic PM, existing MM | 0.880637 | 0.864601 |
| Analytic PM, simple MM ablation | 0.911926 | 0.901616 |
| Market PM, existing MM | 0.879717 | 0.863253 |
| Market PM, simple MM ablation | 0.910473 | 0.899469 |

**Conclusion: simplify PM experimentally while preserving the existing minute/role model; do not replace the minute model with this recent-history ablation.** The analytic PM reduces overall xP MAE approximately 0.95% / 0.72%. Played-player MAE also decreases (1.890859→1.878431; 1.993161→1.982566), as does rotation-player MAE (1.745175→1.724303; 1.849239→1.835609).

That is a promising, modest screen result, not proof the complete architecture is unnecessary. In 2024/25 overall bias worsens from −0.010620 to −0.030572; played-player underprediction worsens in both seasons. The archived B comparator uses 400 Monte Carlo draws while analytic PM does not: reduced numerical sampling noise may explain part of the gain. No fresh high-draw reference or independent prospective calibration claim is made.

The simple MM ablation worsens minute MAE from 10.912877→11.727217 and 10.184831→11.276735. Start-Brier worsens from .072177→.078195 and .067899→.075820. P0, P60 and P90 Brier also worsen. This candidate is rejected, regardless of intuitive simplicity. It retains a frozen B starter prior and existing keeper duration kernel, so it is not a standalone baseline.

## What odds add

Average historical non-closing 1X2 plus over/under2.5 odds from Football-data.co.uk were matched exactly by date and both season-specific club identities. Proportional margin was removed separately for each market; two Poisson goal means were fitted without using target results. Missing/invalid odds fail closed.

Odds add only **0.000920 / 0.001348** MAE improvement over the already simplified PM. Fixture-cluster bootstrap 95% intervals are **[−.005344, +.003242] / [−.005237, +.002538]**; both include no improvement. Rotation-player MAE actually increases relative to analytic PM without odds (1.724303→1.728353; 1.835609→1.840701). These data do not establish a reliable incremental betting advantage.

Team clean-sheet Brier improves .179378→.178823 and .185886→.180337. Team goal MAE slightly worsens in 2024/25 and improves in 2025/26; team goal overprediction bias increases in both. All results, including the unfavorable metrics, are retained.

Crucially, individual odds quote times are absent. Non-closing is not synonymous with pre-FPL-deadline. Thus the market arms may benefit from information unavailable at decision time and cannot justify deployment. No player scorer odds or direct betting model subscription were used.

## Verification and decision

- **84 focused tests passed**, including the existing MM/PM contract, GK empirical kernel, joint roles and penalty separation, plus eight new checks of odds inversion, invalid-input rejection, starter-count projection and analytic scoring/nonappearance.
- Frozen MM marginals reproduce the selected B archive with maximum discrepancy **7.11×10⁻¹⁵** under the locked numerical runtime. The initial unpinned preparation was rejected by this check and discarded.
- Every arm uses the exact same scored player cohort. History is strictly before saved cutoffs using conservative four-hour result-availability proxies; these are not independently observed provider clocks.
- No production files, model parameters, live B forecast, TS inputs or app layout were changed.

No candidate is activated. The analytic PM merits a separate prospective comparison, calibration work and a higher-draw B reference before promotion. A replacement also needs an explicit TS uncertainty contract: marginal analytic means alone do not provide coherent shared scenarios. It does not repair or certify the existing joint substitution process. Market integration additionally requires appropriately licensed, timestamped pre-deadline observations. The present screen answers which simplification is worth pursuing without pretending those integration requirements are complete.
