# Research-based Model B — literature, overlap, data gates and Codex specification
Date: 2026-11-02. Status: RESEARCH DESIGN ONLY. No production change.

## Hard boundary
Keep locked MM, PM/vFinal, TS v3, all historic archived forecasts and published Pages untouched. Model B is an independently labelled research candidate. Do not call the current B-preview Model B in this document: this is a new **research candidate**, named **research-B2** to avoid confusing existing B-MM-PM-TS-v1 production previews. Reuse identities, raw data ingestion, test infrastructure and FPL rules, not unverified parameterizations.

## Verified current implementation and research overlap
- `src/fpl_v1_1_model/attack.py`: `shrunk_rate_per90` already implements positional-prior shrinkage; `event_propensity` uses xM; `allocate_team_event_mean` normalizes individual shares to a team total. A new Bayesian goal head must prove it adds information over these, not merely rebrand existing shrinkage.
- `src/fpl_v1_1_model/joint_simulator.py`: `MatchSimInput`, `PlayerSimInput`, joint match Monte Carlo, FPL scoring incl. saves, penalties, cards, DefCon, bonus; research-B2 must preserve coherent player/team event accounting.
- `src/fpl_v1_1_model/fixture_input.py`, `canonical_fixture_input.py`: fixture/team/player boundaries and explicit source cutoffs. Candidate model must consume strictly predeadline inputs.
- `src/fpl_v1_1_model/role_classifier.py` and historical MM experiments: tactical roles and starter competition have already been investigated. `scripts/build_mm_survival_distributions.py` signals existing survival-related work; audit its exact hazard model before implementing a new one.
- `analysis/results/mm-v2-xi-rating-with-external-ratings-20261006-v1/results-summary.md`: 13,987 reused diagnostic rows, locked MAE 11.487502 vs XI-only 11.477555, ratings model rejected on development state log-loss; not an independent OOS improvement. Provider data included 1,262 unresolved player rows. Do not infer causal lineup contributions from ratings.
- `analysis/results/mm-relative-rating-player-impact-20261006-v1/summary.json`: relative-rating MAE reduction only ~0.0138 min in reused diagnostics.
- `scripts/build_live_pm_observed_team_xg.py`: historical team xG can be summed from played FPL player observations only with strict coverage; it is not guaranteed all seasons have a complete input table.
- `analysis/team_xg_dynamics_experiment.py` and `analysis/team_xg_opponent_adjusted.py` on separate research branch are preliminary single-season probes; DO NOT use as calibrated or full opponent/home corrected comparisons.

## Literature catalogue (verified publication links; method is not itself a guarantee for FPL)
| ID | Literature | Candidate | Added mechanism vs incumbent | Data gap | Decision |
|---|---|---|---|---|---|
| L1 | Holmes & McHale, *Forecasting football match results using a player rating based model* (IJF 2024), DOI 10.1016/j.ijforecast.2023.03.002 | Lineup-conditional team strength | expected XI difference and possibly positions | predeadline lineup probabilities; independently identified player contributions and injury/cross-team attribution | Gate only; high confounding risk |
| L2 | Del Corral, Barros & Prieto-Rodriguez, *The Determinants of Soccer Player Substitutions* (Journal of Sports Economics 2008), DOI 10.1177/1527002507308309 | Competing-risks minute exit hazard | score/time/position-dependent substitutions | exact substitutions, score at decision moment, red cards | First audit existing survival work, then gate |
| L3 | Koopman & Lit, *A Dynamic Bivariate Poisson Model* (JRSS A 2015), DOI 10.1111/rssa.12042 | Dynamic team goal intensities, bivariate score dependence | uncertainty/time variation, score covariance | prior match score available; xG optional; enough seasons for state inference | Viable on match-level data; overlap with existing goals simulator |
| L4 | Böttger & Vischer, *Individual Skill or Just Luck?* (2026 working paper), https://www.wiwi.uni-muenster.de/io/en/en/research/downloads/DP-IO_03_2026 | Persistent player finishing and keeper shot-stopping with partial pooling | empirically disciplined low-variance skill signal | multiple seasons matched players, goals/xG, GK shot quality if available | Promising but only test incremental value vs current priors |
| L5 | Decroos et al., *Actions Speak Louder than Goals* (KDD 2019), DOI 10.1145/3292500.3330758 | VAEP event valuation | actions beyond shot/assist stats | licensed, modern, ongoing full event feed | Defer until actual coverage |
| L6 | Singh, *Introducing Expected Threat* (2019), https://karun.in/blog/expected-threat.html | xT actions/space | progressions into threat zones | coordinates and event actions; historical/live parity | Defer until data licensed/covered |
| L7 | Dixon & Coles, *Modelling Association Football Scores and Inefficiencies in the Football Betting Market* (1997), DOI 10.1111/1467-9876.00065 | Low score correction / exponential time weights | low-score dependence | scores easy, overfit risk; incumbent already match Poisson | Baseline diagnostic, not an automatic replacement |

## Research B2 candidate mathematical contract
Define fixture-level latent variables and condition on predeadline information `I_d`:
- Pre-kickoff team strength `A_h,D_h,A_a,D_a`, opponent/home, projected lineup `L_h,L_a`; attack rates `lambda_h=lambda(A_h,D_a,L_h,L_a,H)`, analogous for away.
- Player start `S_i ~ Bernoulli(p_i(I_d))`; conditional appearance and minutes `M_i` from explicit starter/bench distributions. Optional hazard `h_i(t | score(t),role,availability)` only when timestamped substitution evidence is available.
- Team goals from one joint score/event process; allocate goals and assists by player exposure and relative ability, with constraint `sum(player goal intensities)=team goal intensity` for matching goal channels (penalty vs nonpenalty separated).
- All FPL scoring comes from same simulated match realization; reproducible seeds and player/fixture IDs.
- Report predictive distribution, not only xP point estimate. TS v3 consumes valid compatible distributions without changing its optimizer.

## The first data gate: produce measurable evidence, not guesses
Create a machine-readable matrix for each research field:
`feature,source,license_usable,season,fixture_count,player_fixture_rows,non_null_share,unique_player_match_coverage,mapping_ambiguities,timestamp_source,predeadline_available,leakage_check,downstream_candidate`.
Inspect actual sources: frozen FPL league histories, player fixture observations, team xG derived input, verified external rating ledgers, goal/shot/assist records, substitution events, lineup timestamps. For third-party Wyscout/StatsBomb distinguish retrospective research coverage from ongoing current-PL availability. **Do not substitute today's feed for past predeadline snapshots.**

No numerical completeness claims without reading rows and preserving identity join audit. Reject the player/role model if effective sample size or source completeness fails, irrespective of literature prestige.

## Research program: one isolated contender per mechanism
0. Freeze manifest: all reference hashes, scoring rules, GW boundaries, and source availability timestamps. Maintain strict separation of training, calibration and final evaluation periods; validate across at least two season boundaries where source history permits.
1. Reproduce incumbent metrics, including MM P(start) Brier/log loss, minutes MAE/RMSE, state distribution calibration; PM fixture xG/log score, player goals and assists calibration, point MAE/log score, CS/save/bonus; keep strong baselines.
2. Run **L4 finishing** on current available xG+goals; compare same player/match cuts to existing shrunk rate. Use partial pooling and estimate penalty/nonpenalty separately.
3. Audit **L2 minute survival** for exact event-time availability. If feasible, fit hazard with time-varying score and competing red-card/injury end states. Otherwise do not fake event times from 90-minute aggregates.
4. Test **L3 dynamic goals** with scores (and xG when chronologically available); test both independent and bivariate structure vs the frozen hold model; no peeking into fixture result at evaluation time.
5. Gate **L1 lineup player ability** on measurable lineup shocks and independent player impacts; assess leave-club and leave-season stability. Never sum ratings as causal goal deltas without identification.
6. Only then consider **L5/L6** with ongoing event coverage and rights check.
7. Join only individually accepted mechanisms into coherent B2 Monte Carlo and test interaction effects; never assume component improvements add linearly. Reject if calibration, identities or coherence degrade.

## Promotion rule and outputs
For each contender: write immutable config, source URL and license, training window, evaluation window, code SHA, sample counts, rejected cases, paired/bootstrap intervals grouped by fixture and club, calibration charts, xP deltas, feature leakage report, computational cost. FPL ranking improvement cannot substitute for probability calibration. Report negative results as first-class outputs.

Final promotion requires out-of-time data, no worsening in predefined critical metrics, statistically supported benefit and operational current-season coverage; approval is separate from research. NO merges to `main` or current B-preview without explicit release decision.

## Codex task
`Implement research-B2 only on branch research-model-b2-<date>. Phase 0: inspect existing locked model, feature and source provenance plus every referenced prior experiment. Produce data-coverage.csv and overlap-audit.md before model code. Phase 1: independently implement hierarchical finishing and optional team Poisson baselines with real predeadline training data, never change TS v3 or locked MM/PM. Phase 2: if and only if event and lineup coverage gates pass, implement survival and lineup effects. Use identical GW/cutoffs and paired OOS tests. Report both successes and failures. Do not merge, deploy or change production. Stop and name exact missing fields if any gate fails.`

## Limitations of this research package
Source-code and archive sampling identifies existing pathways but does not certify live provider licenses, full-season raw field coverage, independent player causal effects, or external research models' gain on our xP. These must be measured by Phase 0.
