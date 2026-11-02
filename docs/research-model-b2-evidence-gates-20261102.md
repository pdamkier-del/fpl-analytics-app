# B2 evidence gate — verified repository findings (2026-11-02)

## Executive decision
**Do not build an entire new MM or PM before evaluating the genuinely untested mechanisms.** The repository already contains a survival-duration research implementation, partially pooled attack estimation, a joint Monte Carlo simulator, player-rating competition models and general conversion experiments. The new research model should keep independently useful components and replace only where out-of-sample evidence supports it.

## Audited artifacts and what they prove
1. `scripts/build_mm_survival_distributions.py` reads `selection.json`, requires `selected_duration` begin `survival_`, calls `survival_prediction`, and exports cutoff-safe per-starter hazards to `analysis/results/mm-research-20261014`. **Survival analysis is not new**. Inspect `experimental_mm_research.survival_prediction` and its evaluation before proposing further hazard work.
2. `analysis/results/mm-predictive-distribution-20261017/summary.json`: 39,264 evaluation rows across 2024/25 GW22–38 and 2025/26 GW6–38, but the archive explicitly warns that these are **reused research periods, not independent holdout**, with chronology proxies. Thus they cannot settle a fresh B2 promotion.
3. `analysis/results/dynamic-pm-v2-20261015/summary.json`: PM evaluation contains 2024/25 13,105 player fixture rows; incumbent goals poisson NLL 0.11673369, Brier 0.0283959, xP MAE 0.9483920 in one referenced arm. **Do not compare to MM MAE** or suggest this is a newly independent test; use same arm and cutoff in any pairwise comparison.
4. `analysis/results/general-conversion-20261020/summary.json`: 501 fixtures, 801,600 Monte Carlo draws across arms; individual-only conversion improvement xP MAE approx 0.000464 with interval crossing zero [-0.001068,0.000127] in its 2024/25 slice. **An elaborate finishing model is not automatically an improvement**; review already-tested head and holdout behavior first.
5. `analysis/results/mm-v2-xi-rating-with-external-ratings-20261006-v1/results-summary.md`: 13,987 reused rows, external rating candidates rejected because development state log-loss got worse; 1,262 provider rows unresolved; provider league coverage differs from player identity coverage. **Do not infer causal lineup impact**.
6. `src/fpl_v1_1_model/attack.py`: partially pooled per90 xG/xA and team-normalized attack allocation already exists.
7. `src/fpl_v1_1_model/joint_simulator.py`: already handles shared match events including goal scoring, BPS and penalty outcomes; reject proposals that merely rewrite a simulator to the same event structure.

## Revised ranking (conditional on validated input access)
| Tier | Research question | Existing overlap | Next evidence gate |
|---|---|---|---|
| 1 | Does projected XI improve opponent-adjusted team xG beyond present team model? | Role/XI effects partially tested, but player-derived team strength not independently identified | Train on historically verifiable projected lineups and prefixture individual offensive/defensive contribution ratings; evaluate fixture xG and goals |
| 1 | Can we improve prediction of starting XI/appearance under injuries, lineup shock and workload? | Significant prior role, survival, XI and rating models | Audit provenance and independently hold out a new season; focus 521 known lineup shock examples without tuning on them |
| 2 | Does partial-pooling finishing outperform incumbent conversion? | Shrunk attack rates and conversion tests already present | First independently reproduce archived conversion result; prior intervals straddle zero |
| 2 | Does a dynamic or bivariate score process improve proper scoring rules, CS or BPS? | Match-level simulator already exists | Compare same fixtures/cutoffs with point log score and CS Brier; enforce matched event identities |
| 3 | Do xT/VAEP add predictive information to *current PL* players? | Attack features from FPL only | Require verified longitudinal current-player event data, license and join |
| Defer | Agent-based positional micro-simulation | No established live tracking feed | Do not build from aggregate minutes and xG alone |

## Data audit acceptance questions — per field
- Is there an authoritative source and permitted use?
- Do we have full season(s) of historical data, not 1–2 showcase games?
- Does an immutable historical snapshot prove it existed BEFORE the applicable GW deadline?
- Are player, club and fixture IDs exact and season-aware? Count unmapped and ambiguous.
- Are injury/news timestamps original publication timestamps rather than retrospectively revised?
- Can the feature be refreshed reliably for future GWs with zero human screenshots?
- How does feature availability differ for newcomers, transfers, international/cup fixtures and DGWs?
- Does it represent independent information beyond existing PM/MM inputs?
- Can all model outcomes be evaluated on identical cases with identical scoring rules and cutoff?

## Minimal real go/no-go outputs for Codex before new mathematical code
1. `research-b2/datasets.csv`: source, license, exact columns, historical availability timestamp, fixtures, players, matched/missing rows by season, cutoff leakage count.
2. `research-b2/incumbent-overlap.md`: detailed code-path and mathematical duplicate check for research catalogued candidates.
3. `research-b2/baseline-reproduction.json`: reproduce frozen prediction metrics before changes with checksums.
4. `research-b2/candidate-approval.csv`: ACCEPT FOR RESEARCH / DEFER NO DATA / REJECT REDUNDANT plus reasons for each candidate.
5. Branch-only tests; no production deployment, no merge to main, TS v3 unchanged.

## Codex launch text
> Continue `pdamkier-del/fpl-analytics-app` from `research-model-b-design-20261102`; read `docs/research-model-b2-plan-20261102.md` and `docs/research-model-b2-evidence-gates-20261102.md`. Create your own isolated B2 implementation branch. First produce audited coverage and exact incumbent overlap; do not claim survival, shrinkage or joint simulation are new methods. Reproduce old baselines with their caveats, and propose the *smallest independent experiments* likely to improve xP and probability calibration. No deployment or locked-model changes. Stop and report precise missing input fields if data gate fails.
