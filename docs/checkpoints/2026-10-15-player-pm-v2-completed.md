# Player-based PM v2: phases A/B completed

PR #3, branch model-audit-optimization-20261012. Start adf948f. Production untouched; locked_model_active=false.

Primary matrix 38729720330 / 852f237: all 18 jobs passed, 330 fixtures per season/MM arm, 400 draws, 1,584,000 historical match draws. Selected simple/hierarchical half365/strength5 and hybrid h=.25, beta=.25 using 2024/25 GW6–21 only. Later evaluation uses 2024 GW22–38 and 2025 GW6–38; reused periods, not pristine holdouts.

Locked-MM original vs hybrid xP-MAE: 2024 .9477938 → .9495469; 2025 .9291727 → .9295283. Hybrid RMSE improves, but MAE gains are not established. Hierarchical assist log-loss improves both seasons. Under experimental MM, 2025 hybrid MAE worsens .9234618 → .9269759 with paired CI excluding zero. Do not promote.

Focus 38730402769 / 3725a64 passed, frozen 12 October cutoff. Original/hybrid xP: Haaland5.68156/5.62281, Palmer3.86313/4.88562, JoãoPedro3.35500/3.25594, Saka5.57219/5.21344. These are repeated-seed research means, not a new live forecast or private manager plan.

Mechanisms 38766320676 / c6bb60b passed, 532 tests in22.58s. Exact Shapley attribution: 2024 goal/assist improvements offset by CS deterioration. Under experimental MM2025, goal/assist deterioration dominates instead. Finishing-off analytic proxy helps2024, hurts2025; no stable improvement. Jensen/independent-XI check finds illegal starter counts; test existing legal joint-XI candidate with BOTH PMs next. Attribution is not causality.

Nine original report hashes and current point sums verified. Full model audit38766116114 oned27477 passed. See docs/audits/2026-10-15-player-pm-v2.md and analysis/results/player-pm-v2-20261015/{validation,evidence_manifest}.json. All numeric reports committed; do not rerun completed matrix unnecessarily.

Remaining: new independent validation, actual historical publication clocks, source/BPS/MM certification, multi-season compatible npxG and creator links, tactical/club transition bridge, joint-XI interaction, missing150/183 historical six-GW cells for candidate TS. Original2125 /44 transfers /28 hit points preserved. No private manager data, production merge or app deploy.
