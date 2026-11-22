## Completed: all-club historical MM evaluation

**MM only.** No PM, FPL-point, TS or chip simulation/change. Production sources and the 2,125-point benchmark remain unchanged; `locked_model_active=false`. Keep this research PR draft.

### Coverage and protocol
- All **20 clubs in each season**: 2024/25 GW22–38 and 2025/26 GW6–38; **39,264 identical evaluation player-fixtures per arm**.
- 2024/25 GW6–21 is separately reported as reused development evidence. GW1–5 lack frozen MM forecasts and are not claimed tested.
- **Nine arms**: five requested references/candidates plus isolated return/full-role and existing starter-duration alternatives. **540 club/model/phase records**, with **10 largest errors for each (5,400 rows)**.
- Every frozen player-fixture matches Core identity, club, GW, actual starts and minutes; all models share keys/truth/cutoffs. Eligible news is strictly predeadline. Existing historical outcome-publication clocks remain kickoff+3/4h proxies.
- Paired 1,000-draw moving **4-GW** bootstrap, retaining blank club calendar weeks; seasons independently resampled for pooled intervals. Sparse groups under eight populated GWs have no invented interval.
- These periods were previously reused in research, **not independent holdouts**. No new fitted model parameters or player/club boosts.

### Pooled evaluation

| MM | Minute MAE | RMSE | Appearance Brier | False-zero appearance |
| --- | ---: | ---: | ---: | ---: |
| Original locked | 11.241 | 21.116 | .08436 | 0 |
| Individual role | 11.029 | 20.931 | .08191 | 19 |
| Role + news | 10.682 | 20.667 | .07903 | 35 |
| Role + source-chance cap | 10.528 | 20.437 | .07676 | 35 |
| Chance cap + preserved return starter-duration | **10.521** | **20.417** | **.07676** | **35** |

Fixed candidate vs original: **−0.719 minutes MAE [−0.889, −0.604]**. All 40 club-season point estimates improve; not every club CI excludes zero. The large 2024 improvement includes repair of missing availability data.

### Findings and isolated tests
- Start-selection algebraic errors dominate; rotation/short-history groups are hardest. Reports include regular/reserve biases, prior three full-start cohorts, one-short-start reaction cohorts, and focal City/Chelsea/Arsenal/Liverpool analysis.
- First **1–3 scheduled matches** after a sourced selection return and first **1–3 actual appearances** are evaluated separately. Actual-appearance cohorts are retrospective only, never forecast inputs. Medical/training clearance is not inferred.
- Existing role starter-duration **for all players** worsens MAE by **+0.323 / +0.406 minutes** versus the chance control, while improving RMSE. Reject as a universal MAE improvement; preserve the documented loss-function tradeoff.
- Preserving only starter-duration on return gives a small 2025 gain, uncertain in 2024. Full pre-injury tuple carry worsens return forecasts.
- **35 false-zero appearance cases** remain; theoretical log-loss is infinite at contradictory endpoints. Reported finite loss uses the explicit 1e−12 numerical clip.
- Three DGW suspension mechanisms have retrospective primary-source corroboration (Jones, Nketiah, Guéhi). The official articles postdate the GW deadlines and are **not** injected into forecasts. A fully verified fixture-scoped expiry intervention remains **Not Available**; no guessed year/time, health clearance or probability floor is introduced.

### Results and reproducibility
- [Main all-club report](https://github.com/pdamkier-del/fpl-analytics-app/blob/research-role-injury-club-audit-20261016/docs/research/2026-10-16-mm-all-clubs-results.md)
- [All 20 clubs 2024/25: five main arms, groups, returns, top ten errors](https://github.com/pdamkier-del/fpl-analytics-app/blob/research-role-injury-club-audit-20261016/docs/research/2026-10-16-mm-clubs-2024-25.md)
- [All 20 clubs 2025/26](https://github.com/pdamkier-del/fpl-analytics-app/blob/research-role-injury-club-audit-20261016/docs/research/2026-10-16-mm-clubs-2025-26.md)
- Complete CSV/JSON and manifests: `analysis/results/mm-all-clubs-20261016/`. Large CSV/JSON files use gzip; compare decompressed content, not codec bytes.
- Scripts: `validate_mm_all_clubs.py`, `report_mm_all_clubs.py`; permanent MM/source capsule reused from PR #4/#8.
- [Full all-club workflow 38929682699 — passed](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38929682699): **46 regressions**, all-40-club coverage, data hashes, unchanged frozen forecasts and unchanged production `src`.
- **All seven numerical output contents reproduce byte-for-byte locally vs CI**, with no numerical tolerance/rounding.
- Code commit `297d0f4`; permanent result commit `bd1ee8a`; reports/reproduction commit `0233e85`; reproducible Markdown renderer/final HEAD `02e776a`.

### Source layer and remaining gates
Strict news matching across all GW6–38 origins remains **99.59% /99.68%**; 349/357 observed FPL-medical episodes and 282/294 source selection returns. These are not clinical diagnoses or clearance. Zero verified training-return statements. Immutable FPL archive versions/identities and independently bounded GitHub PushEvent clocks are preserved in manifests; mutable current articles are diagnostic corroboration only.

**Recommendation:** retain production MM. Continue prospective/unused MM validation and authoritative fixture-specific disciplinary/medical sourcing. No live certification, app promotion, independent-holdout claim or PM/TS/FPL-point benefit is asserted.


---

## Multi-competition workload and match importance — completed supported analysis

Both green inventory artifacts were downloaded and SHA-256 verified; permanent ZIP capsules are preserved. The earlier XI inventory used player-name fallbacks and misclassified PL. The new analysis requires stable IDs and respects all 40 quarantines.

- **35,735 player observations; 1,840 team-games; 1,743 complete XIs.** 2024/25: 1,033 complete XIs across PL, CL, EL, Conference, FA and League Cup. 2025/26: all 760 PL XIs and 10 League Cup XIs; European XIs incomplete, FA Cup absent.
- **Observed 2024/25 substitute entries/game:** PL 4.220; CL 4.109; EL 4.167; Conference 4.154; FA Cup 4.443; League Cup 4.508. These are recorded lower bounds. Entry/exit causes are not invented.
- **XI changes from previous recorded match:** PL 3.046; CL 3.413; EL 4.567; Conference 8.462; FA Cup 4.918; League Cup 6.557. Cup XI turnover is distinct from in-match substitutions.
- Retrospective ridge test controlling club, rest, recorded 7/14d load and empirical previous-XI role/continuity: adding competition/stage reduces **XI-turnover** MAE **1.550138 → 1.471993**; paired delta **−0.078145**, four-week block-bootstrap 95% CI **[−0.150850, −0.008496]** (502 later observations). This is **not minute-MAE**, a causal importance result, or a deadline-certified forecast. Reused research season, not untouched holdout.
- Existing frozen MM A reproduced over **39,264 player-fixtures / all 40 club-seasons**: minute-MAE **10.521392**, RMSE **20.416725**, start-Brier **0.070115**.
- **New B/C/D MM arms NOT RUN / Not Available:** missing 2025 FA Cup, quarantined/overwritten European keys, missing IDs/kickoffs, historical publication timestamps, predeadline future schedules/tie states/opponent-strength versions. No substitute synthetic numbers, importance weights or partial replay labelled complete.
- Exit substitution counts and universal exit times unavailable. Only 42 team-games have minute-concordant source intervals; do not infer exit cause from short minutes.

### Verified execution and files

- [Full scientific report, all clubs, limitations and reproduction commands](https://github.com/pdamkier-del/fpl-analytics-app/blob/research-role-injury-club-audit-20261016/docs/research/2026-10-16-mm-match-importance-results.md).
- Results: `analysis/results/mm-match-importance-20261016/`: complete observed team/player CSVs, 280-row coverage matrix, before/after PL tables, controlled association, 40-club A/gates table, JSON/checksums.
- [Actions 38941461600 — passed](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38941461600): **52 focused MM/source tests**, actual analysis, archive restore, frozen A replay, unchanged production src and prediction hash; results committed at `915bfea`.
- Seven numerical result contents reproduce byte-for-byte locally/CI. Three regression-containing files reproduce within **5.05e−12** (checked tolerance 1e−9), after tightening LSQR tolerance to 1e−12. Full evidence in `reproduction.json`.
- Code `31b736a`; solver `74645ce`; final report/checkpoint `b97d7c1`.

**Recommendation: retain existing MM.** No documented MM improvement from importance yet. Production MM/PM/TS/chips and benchmarks unchanged, `locked_model_active=false`; no PM, TS, FPL-point or chip simulation run.


---

## Club-specific dynamic priority — executed A/B/C/D comparison

[Full report and all-club tables](https://github.com/pdamkier-del/fpl-analytics-app/blob/research-role-injury-club-audit-20261016/docs/research/2026-10-16-mm-club-dynamic-importance.md)

Seven levels were implemented: control, objective sports context (A), pooled historical player use, club-specific historical player use (B), combined (C), dynamic relative competition use (D), and D with extra normal-player workload controls. Both prior-objective and existing preserved MM roles are tested; no named/manual star boosts. Unknown absence is not called deliberate rotation.

**Actual scope:** 2024/25 reliable multi-competition data; 898 matched team-games per role, 398 pre-Jan development /500 later evaluation, 19,756 individual source rows and **98,000 predictions**. Existing role coverage averages86.8%, with explicit objective fallback. Roles and all historical usage inputs precede the current cutoff. Current XI, result and minutes are labels only. Nine new tests cover leakage, unknown availability/minutes, regularization, PL anchoring and fail-closed consumers.

| Endpoint | Control | D_dynamic |
| --- | ---: | ---: |
| Normal-starter-share MAE, objective roles | 0.118676 | 0.108676 |
| Same MAE, existing roles | 0.110482 | 0.111708 |
| XI-changes MAE, objective roles | 1.735746 | 1.900345 |
| Start Brier, explicitly available objective-role players | 0.126327 | 0.149106 |

Objective normal-share delta is−0.010000 [−0.015502,−0.004168], but existing-role delta+0.001227 [−0.005540,+0.008690]. Club-specific historical effects add no robust marginal value (objective B_club vs B_global−0.001121 [−0.002963,+0.000693]; existing roles worsen). Alpha is selected chronologically per endpoint, not shared indiscriminately. Reused research/evaluation periods are not untouched holdouts.

**Conclusion: retain control /production MM.** D_dynamic objective remains only an isolated secondary research candidate. Observed between-club usage differences do not identify subjective or causal coaching priorities. Conference has only Chelsea, limiting separate club/competition identification. Sparse/unseen club-competition intervals are Not Available, not falsely precise. Focal Chelsea/City/Arsenal/Liverpool/Villa/Spurs monthly tables and all20 clubs are in the report.

- Clean team and individual pre-match exports omit current labels and include IDs, cutoffs, estimates, uncertainty and source/timing metadata.
- **Every export is diagnostic, deadline_correct=false**; strict consumer rejects it. 2025 FA absence, European ID/quarantine issues and historical publication/schedule/tie-state gaps remain; no fabricated full2025 test.
- [Actions38961530083 — passed](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38961530083): **61 regressions**, actual model execution, unchanged production src and frozen MM checksum.
- Artifact12073510644 downloaded and ZIP/content hashes checked. All13 manifest outputs/gzip streams validated. Separate local replay: six contents byte-identical; seven numerical within1.552e−8 maximum, checked at1e−6 tolerance.
- Code `e7422b1`; results `9fae5f8`; report/checkpoint `3b10c50`; final report postprocessing `aca5dba`.
- Reproduction JSON in docs/checkpoints; report renderer reproduces tables and paired overall contrasts. Superseded label-bearing legacy feature filename removed.

**No full MM, PM, TS, FPL-point or chip simulation. No production changes. locked_model_active=false.**

