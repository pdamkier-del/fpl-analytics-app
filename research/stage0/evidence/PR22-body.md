Unavailable players could regain future minutes, B workload features discarded known cup minutes, and own goals did not consistently affect the shared score and clean sheets. The isolated B preview now repairs those paths. Production, frozen NP coefficients and locked TSv3 remain unchanged.

Published and verified: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/overview.html#dashboard

- Persistent eligibility across every position and six GWs; probabilistic dated injury returns, with the first recorded PL appearance explicitly identified as the return proxy.
- Consistent historical/current physical features from verified PL/cup/UEFA observations. Historical coverage and clock proxies remain explicit.
- Conserved ordinary/penalty/own-goal events, scorer checks and active-taker penalty budgets. Conditional penalty conversion already existed in B and is retained.
- G/xG and constrained exact TS alternatives tested; undocumented team/TS changes are not activated. Special assist occurrence rates and red-card removal remain documented limitations.

Validation: 1,111 Python tests and 31 JavaScript suites; 341 historical fixtures / 27,092 player-fixture rows per arm / 400 draws. Frozen B reproduced with maximum xP error 0. Combined xP MAE 0.890843→0.889531 and 0.875883→0.873200. Gains are small; start/minute metrics are slightly mixed and first-season xP improvement is not established by its confidence interval. Scorer bias improves; absolute assist bias worsens slightly.

Fresh one-match/GW/six-GW checks and deterministic repeats pass. Synthetic TS/chips complete without changing manager-state. All 106 currently status-u players have zero future minutes/points. Public mobile/desktop browser checks verify probability cards, profiles, MathML, and a shared forecast across MM/PM/TS; no real private plan POSTs. All 88 production files preserved byte-for-byte; eight HTTP production assets independently unchanged.

Numerical source is pinned to 161b67b6fb8786a38e78c245b92a03ad841575d8. The final documentation commit adds evidence only. No production merge or activation.

- [Delivery report, player before/after and evidence](https://github.com/pdamkier-del/fpl-analytics-app/blob/736d65cacc1afeeaf8c3dcfad317d7ee745b48fa/docs/checkpoints/2026-11-01-integrated-repair-DELIVERED.md)
- [Full numerical CI](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/41216503954)
- [Initial publication](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/41223882607)
- [Verified automatic refresh](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/41278968979)

