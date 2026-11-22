# Individual MM refinement checkpoint

Branch: research-individual-mm-refinement-20261016. Draft PR #9 stacked on PR #8 branch, parent aca5dba. Start with docs/research/2026-10-16-individual-mm-refinement.md and adjacent reproduction JSON.

All11 MM arms executed on both seasons, all40club-seasons, 39,264 matched evaluation player-fixtures per arm. Original/best reference plus A/B/C/D and A_B/A_C/B_C/B_D/A_B_C_D. New learner origins use only earlier known labels. 2024/25GW14-21 reused development selection; evalGW22-38 and2025/26GW6-38, NOT independent holdouts.

B wins as research candidate: MAE10.5213916382 ->10.4083581000; paired95% delta[-0.1483446264,-0.0745342353], startBrier.0701154096 ->.0688269150. Both seasons improve. 31/40club-seasons improve; nine worsen in point estimate. Unadjusted club harm flags: Everton2024/25, Newcastle/Wolves2025/26. No supported harm in pooled critical role/return/rest groups, not proof of non-inferiority. Recommend B for new validation, not unconditional production integration. A/C worsen MAE; D has no clear incremental gain; B+D not better than B.

Conditional duration C improves s/c MAE but worsens overall mixture minute-MAE; report decomposes the paradox by actual outcome. All35 hard-source appearance conflicts persist. Do not invent availability, suspension expiry or clinical clearance to remove them.

72 regressions pass locally/CI. Actions38966504511 succeeded, code8cb2c3e, numerical results ea0b2ec. Artifact12076020691 ZIP/hash verified. All13 output contents are byte-identical between local and clean CI, including canonical decodedNPZ; no numerical tolerance needed. Original frozen forecast hash and production src unchanged. MM ONLY: no PM/TS/FPL-point/chip runs. locked_model_active=false.

Report renderer and derived decisions/ablations are saved separately from immutable numerical result manifest. Prior-only features exclude actual truth columns; prediction archives contain truth for research only. Legacy existing unrelated local modifications in fa-match-importance CSV gzip and phase5e_core part0001 were left untouched; never include them in commits for this task.
