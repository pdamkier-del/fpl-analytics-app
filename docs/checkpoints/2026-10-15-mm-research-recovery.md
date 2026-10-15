# MM research recovery, 15 October 2026

Continue PR #3 / model-audit-optimization-20261012 from latest remote HEAD. Do not reset production or repeat completed simulations. Production base remains 2b1983a; locked_model_active=false.

## Verified completed work

- Original simulator correctness candidate and its original seasonal A/B remain isolated; see 2026-10-13-simulator-correctness.md.
- Full MM attribution/start/survival/PM/context workflow 38565961308 passed at 892fad1. Two 330-fixture PM matrices, all original references exact, 505 tests at that source commit.
- Artifact reports recovered by workflow 38711276013. All five exact original file hashes are checked in analysis/results/mm-research-20261014/evidence_manifest.json. Full PM reports and score-context report are committed, not estimates reconstructed from memory.
- Most promising point candidate: development-selected logistic_1.0 + survival_42.0_2.0 full duration distribution. Test xP-MAE 2024 GW22-38 .947793781→.932798169; 2025 GW6-38 .929172656→.923461810. Point RMSE and played-player errors improve, raw analytic 2025 minute MAE worsens. No promotion.
- Hard availability ablation improves aggregate errors but has 19 source contradictions and slightly worse played-player point error/log-loss. All 19 rows reverified against Core and saved in out_state_actual_minutes.csv.
- Score-context hazard improves RMSE but worsens minute MAE both seasons. Full context-PM/TS remains unavailable. Do not present lost/uncommitted secondary medical/calendar experiments as completed evidence.
- Haaland exact raw MM: .8382304242*80.2773039531 + (1-.8382304242)*.4207609277*14.8523640260 =68.301824263. Last79-minute start receives88.39% of weight under original .321926-match half-life.
- Current focus original-PM rebuild passed workflow38712316437 at3838f836. This uses frozen12October cutoff, 3fullfixtures, 8x400draws. Original firstseed allplayers exact, component rebuild tolerance1e-10. Haaland original/candidate xP5.6815625/5.666875 and simminutes67.6696875/70.8496875; Saka xP5.5721875/5.4459375. Chelsea goal intensity unchanged1.342868819888325. Summary/provenance committed; full report/input in mm-current-pm-focus artifact.
- 510 Python regressions passed locally after final alias/dataclass-guard corrections. Classic manager, profile snapshot and deadline JavaScript checks passed. Full audit atf8bd1f9 passed workflow38711275817. Later full-audit runs may still be completing; check status before claiming current HEAD's own workflow passed.
- Research CSV/JSONL captures now atomic, fsync'ed and gzip-trailer validated. Adapter corrections use original assembly; production code/coefficients/strategy unchanged.

## Remaining acceptance blockers

Independent unused test period; historical publication clocks, roster/medical/exit sources and full workload; complete historical six-GW future forecast cells (no candidate TS season points); combining MM distribution with exact-XI/shared-goal candidate and physical coverage checks. Original TS accounting benchmark2125/44transfers/28hitpoints preserved, not candidate acceptance. No production deploy/merge/certification/private manager state.
