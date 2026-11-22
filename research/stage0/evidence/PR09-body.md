## MM-only follow-up to #4 and #8

**Recommendation: advance B alone to independent/controlled integration validation, not production.** Production sources/parameters and original forecasts remain unchanged, `locked_model_active=false`. Keep draft.

[Scientific report: mathematics, all clubs/groups, negative results and reproduction](https://github.com/pdamkier-del/fpl-analytics-app/blob/research-individual-mm-refinement-20261016/docs/research/2026-10-16-individual-mm-refinement.md)

### Executed scope

- Original locked MM, best existing `role_chance_return_duration`, isolated A/B/C/D, A+B, A+C, B+C, B+D and A+B+C+D: **11 arms**.
- **39,264 identical evaluation player-fixtures per arm; all40 club-seasons** in2024/25GW22–38 and2025/26GW6–38. Full archive contains50,231 source rows/arm, including development.
- Prequential learners refit at each cutoff using only labels whose known-at precedes it. 2024/25GW14–21 selects hyperparameters. Previously reused research/evaluation periods are **not independent holdouts**.
- Existing frozen forecasts replayed exactly; new candidate predictions actually fitted/calculated historically, not fabricated forecasts for unavailable GW1–5.
- MM only: **no PM, TS, FPL-point or chip execution**.

### Actual pooled results

| Arm | Minute MAE | RMSE | Start Brier | Clipped start log-loss |
| --- | ---: | ---: | ---: | ---: |
| Original locked | 11.240711 | 21.115962 | .073445 | .241262 |
| Best existing | 10.521392 | 20.416725 | .070115 | .231354 |
| A stable role blend | 10.676534 | 20.123737 | .069301 | .227795 |
| **B learned start calibration** | **10.408358** | **20.172026** | **.068827** | **.226125** |
| C personal duration distributions | 10.809961 | 20.220984 | .070115 | .231354 |
| D extended sourced return carry | 10.520169 | 20.310755 | .069947 | .230472 |
| B+D | 10.441749 | 20.173871 | .069335 | .227393 |

B vs best: **−0.113034 minutes MAE, 95%[-0.148345,−0.074534]**; startBrier−.0012885 [−.0016937,−.0008726]. Both seasons improve:11.156276→10.948646 and10.203330→10.137688.

**Club/critical-group caveat:** B improves31/40 club-season point estimates and worsens9. Unadjusted positive MAE intervals flag Everton2024/25, Newcastle2025/26 and Wolves2025/26. No supported deterioration in pooled critical role/return/rest screens is not proof of non-inferiority. Sparse groups retain Not Available intervals. These club findings prevent unconditional integration; no posthoc club switches or manual player boosts.

### Methods and negative findings

- A separates long normal role from temporary absence using the existing role priors/decay, then tests a fixed extra blend. B reuses the same history but learns start-probability calibration.
- Historical observed participation may establish past selection evidence without declaring future health. Unknown absence does not become tactical bench evidence. Hard source/outcome conflicts are quarantined from normal-role/duration training and retained in evaluation.
- Workload follows canonical player identity across known PL club moves; normal-role/personal-duration history remains club-specific. All-competition workload remains incomplete, not imputed as zero.
- C learns residual corrections to existing s/c, then a bounded discrete empirical personal/position-duration mixture. Conditional starter/cameo MAE improves8.064556→7.873829 /11.348578→10.899898, **but total minute-MAE worsens**; the report gives an exact outcome-stratum decomposition. No invented substitution cause or game-state hazard.
- D requires prior sourced medical OUT/suspension and fresh AVAILABLE; no clinical/training clearance inference or actual target appearance as input. The existing best candidate's established return-duration protection is preserved; the new extended p/s carry adds no robust MAE gain.
- B+D is not better than B alone: paired ΔMAE+.033391 [−.002279,+.076744]. Simpler B is preferred for further validation.
- **All35 source-hard-zero appearance conflicts remain** (32OUT,3SUSPENDED). No unsupported expiry, guessed health state or artificial probability floor repairs them. Contradictory hard probabilities still have infinite theoretical log-loss; displayed loss explicitly clips at1e−12.

### Evidence and reproduction

- [Actions38966504511 — passed](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38966504511): **72 MM/source/leakage regressions**, actual11-arm/40-club execution, unchanged production `src` and original forecast checksum.
- ZIP artifact12076020691 downloaded and SHA-256 verified. All**13 output contents** reproduce byte-for-byte locally vs cleanCI, including canonical decodedNPZ predictions and decompressedgzip data. No numerical tolerance/rounding needed; container bytes are not claimed identical.
- Result CSV/JSON/NPZ: `analysis/results/individual-mm-refinement-20261016/`; report-derived decisions/ablations separately under `docs/research/data/`.
- Input/known-at proofs, per-origin fit counts, all club/group metrics, calibration bins, duration forecasts, all35 source conflicts and top errors are preserved.
- Code `8cb2c3e`; numerical results `ea0b2ec`; report/checkpoint `012b525`.

**Remaining gates:** unused/prospective MM validation; three club-risk flags;35 hard-source conflicts; inherited outcome-publication proxies; missing verified fixture-scoped suspension expiry, medical/training detail, substitution events and complete cup/Europe workload. No production approval or FPL-point benefit asserted.

