Status: **NOT READY** for live activation. This extends PR #15 without changing production MM, PM, TS, chip rules or the 2,125-point benchmark. `locked_model_active=false`.

Implemented:
- Exact-identity/cutoff B → locked vFinal minute-input adapter; simulator-object checks preserve every non-minute parameter.
- Guarded six-GW B → PM → original private TS entry point, with official fixture/catalogue/source-clock checks, immutable forecast identity and no public manager results.
- Real end-to-end regression using explicitly synthetic inputs: 576 MM player-fixtures, 18 matches, 96 players, six GWs and a legal manager squad. No mocked simulator or planner; this is not a personal or historical TS result.
- Corrected prospective registration clock (cutoff ≤ registration < official deadline), immutable receipts, final-document integrity and code identities.
- Published historical PM comparison, matched player-popup xP, model explanations and responsive test selector.

Verified evidence:
- 39,264 historical MM predictions reproduce the existing B comparison: minute MAE 11.240711 → 10.408358; RMSE 21.115962 → 20.172026; start Brier .073445 → .068827; >60-minute errors 1,559 → 1,278.
- Actual paired locked-PM replay: 11,794 player-fixtures / 144 fixtures, 2025/26 GW22–38, 400 draws each. xP MAE .918241 → .881045, RMSE 1.845620 → 1.811052. These are reused diagnostic data, not independent validation; temporal intervals do not include all Monte Carlo uncertainty.
- [643-test CI and complete replay](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39019030796), validated code `243612f107ebeedf1ee1f10846c513c364fa9154`. Final evidence documentation commit `0a3ef86a0555365d5ad9abf6a13d51304c923506`.
- [Successful protected Pages publication](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39019066592). All 88 production files outside mm-preview remained byte-identical to the original production artifact.
- Browser verified: MM → PM player popup; legal 11-player expected XI with one GK; search/filter/sort/reload; Pitch/List; 390px responsive iframe with no document overflow. Not a physical Safari test.

Confirmed activation blockers:
1. The unchanged PM samples rounded/clipped Gaussian durations: starter cap90, cameo cap45. Its mean does not equal B's supplied conditional mean. Analytical discrepancy averages −.728064 minutes overall, −3.014520 for B xM>60. A certain starter with input90 produces about86.01 PM expected minutes. The preview exposes both values; no silent sampler replacement or B reparameterization.
2. No verified current PR8 role/chance/return-duration feature producer and current candidate backend/app manager route. Legacy/vNext cannot be renamed B. Real current captain/transfers/chips remain Not Available.
3. No untouched prospective validation; PMF calibration/proper-score gate, historical source contradictions and inherited source-clock/formation gaps remain.

Public source capture is installed on main and has successful **push** runs; no scheduled run has yet been verified. Its receipt explicitly says forecasts_registered=0 / BLOCKED_CURRENT_B_FEATURES. Source capture is not a prospective MM forecast.

Report: [final integration findings](https://github.com/pdamkier-del/fpl-analytics-app/blob/integration-mm-final-chain-20261017/docs/research/2026-10-17-mm-locked-chain-validation.md). Preregistered protocol and evidence checkpoint are linked there. No production activation or merge is requested.

[Published MM preview](https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/) · [Historical PM comparison](https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/chain.html)
