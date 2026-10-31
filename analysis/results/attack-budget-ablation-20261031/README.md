# Offline investigation of MM → PM → TS weaknesses

Research only. Production, the public B model, all model source files and manager state are unchanged. This extends the user's requested comparison of individual forecasts with team-normalized attack allocation. It is not a search for a bespoke Gibbs-White correction.

## Fixed experiment

Prepared 341 historical fixture inputs from 2024/25 and 2025/26, GW22–38. These periods have already been used in previous research; they are not a fresh independent holdout or complete-season coverage. The input task archive has a recorded checksum. Current normal-match physical minutes, roles, separate penalty process, scoring rules and bonus engine are retained. Every arm recomputes point and bonus outcomes jointly rather than replacing a displayed number after simulation. Four hundred draws are used per fixture and arm. MM analytical means are asserted identical between arms; finite-sample minutes may fluctuate.

The common baseline is freshly simulated using the active normal timeline. It is not the older October24 physical-candidate forecast: a smoke comparison showed that earlier archive is not numerically identical. All candidate comparisons therefore use the same fresh baseline, not mismatched archived scores.

Arms are fixed current, equal blend, individual NP/xA rates and a current-architecture assist probability smoothed with 50 prior goal observations. Goal rates use the existing separated nonpenalty posterior; penalties remain separate. The individual/raw xA arms are sensitivities, not target-equivalent FPL-assist forecasts. A separately declared extension converts xA to FPL-assist scale using only prior-known observations, with 50 prior xA of shrinkage to an earlier-season ratio. No conversion or blend parameter is selected from the scored fixtures.

The research-only simulator extension copies exactly one AST probability lookup in memory to permit a different assist probability per team. The original module is never edited. Exact 32-draw full-result identity is asserted for the first fixture of each season when the extension uses the original probability. All other event allocation, captain-independent player scoring, bonus and physical substitution code stays in the existing simulator. Assist probabilities are capped at one; audit rows identify where an individual assist budget exceeds ordinary goals. This preserves one assisted ordinary scorer event, not arbitrary independent points.

Metrics: xP RMSE and MAE/bias, separate goal/assist MAE, bias and Poisson NLL, bonus MAE; all, actual-played, attacking-position and fixed baseline-high-xP cohorts. Fixture-cluster bootstrap intervals compare candidates with the same baseline. Monte Carlo zero-rate NLL is numerically floored and is diagnostic. No live promotion follows from this reused retrospective screen alone.

## Other verified findings

- Public João Pedro forecast already has zero minutes/xP and frozen official injury status. The earlier chat lineup naming him as starter/vice-captain was an assistant mistake, not a missing model injury.
- Jackson's 66.5 expected minutes include an approximately 15% non-start chance. Conditional starter duration is about 78 minutes. A comparison against only his last few starts cannot establish bias.
- Current input provenance explicitly declares PL-only workload/last-start features, verified all-competition starter-role history, and no structured coach statements. All-competition tactical roles do not establish all-competition explicit fatigue features.
- Existing partial BPS coverage remains a limitation; a high bonus forecast is not independently validated by component sums reconciling.
- Current TS uses exponentially decaying six-week weights and a heuristic candidate pool. Its accounting can be correct while candidate search or uncertain forecasts yield a weak recommendation. See the separate read-only transfer audit; private inputs/results are not committed here.
- 81 existing physical-timeline, joint-role, unified-chain and snapshot-policy tests passed during this investigation. The earlier transfer audit passed 31 targeted tests.
