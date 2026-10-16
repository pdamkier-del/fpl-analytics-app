# Club/dynamic importance research checkpoint

PR #8, research-role-injury-club-audit-20261016. No full MM simulation; no PM/TS/FPL points/chips executed or production changes. locked_model_active=false.

Read docs/research/2026-10-16-mm-club-dynamic-importance.md. Seven priority levels (control, A_objective, B_global_history, B_club_history, C_combined, D_dynamic, D_individual), two role definitions, three team responses and individual starts executed. 898 matches per role, 398 pre-Jan development /500 later evaluation, 98,000 predictions. Existing roles use 86.8% sourced preserved role profiles on average, otherwise objective fallback. Unknown absence not intentional rest.

Dynamic objective roles improve normal-XI-share MAE 0.118676 ->0.108676, but existing roles 0.110482 ->0.111708 and available-player Brier worsens. Own club history gives no robust marginal value. Keep control; D_dynamic objective only a secondary isolated research arm. No production promotion or independent holdout claim.

CI 38961530083 passed61 tests and all candidate execution steps. Code e7422b1; numerical results9fae5f8. Artifact12073510644 is checksum-verified. Separate local replay verifies all13 outputs; six contents exact, other seven numeric maximum1.552e-8 with tolerance1e-6. Details in adjacent reproduction JSON.

Clean team and individual pre-match files exclude current outcome labels; strict consumer rejects every row because historical source/publication/program gates remain incomplete. Full all-competition2025 remains blocked. Do not treat the reported percentage-point usage contrast as subjective importance or as a probability of a strong XI.

Two pre-existing local modifications were left untouched: analysis/results/fa-match-importance-20261006-v1/all_features_fa_mi.csv.gz and model/checkpoints/phase5e_core/parts/core.gz.part-0001. Do not include them in commits for this research task.
