# Live role integration — 2026-10-09

## Exact implementation
- The Publisher first fetches official FPL `bootstrap-static` including current player **code**, FPL element ID and team **code**, next GW and publication timestamp.
- `scripts/build_live_role_snapshot.py` collects confirmed, *finished* 2025/26 lineups, formation, positional geometry and actual minutes strictly before the observation time.
- The existing locked `fpl_v1_1_model.role_classifier.classify_lineup` assigns the source-grounded historical roles; the locked `RoleHistory.state` calculates the historical recency-weighted q(role), H(role) and evidence.
- Cross-season identity is joined by stable FPL player `code`, never volatile season-specific element IDs or fuzzy names.
- If a player transferred clubs, previous positional q can be retained as a documented prior; previous-club H is **discarded**, never presented as current-club competition.
- The forecast UI `app/index.html` displays source-labelled q, H and role: `2025/26-prior` vs confirmed current-season, and generic FPL position when evidence is missing. No array-index fake roles.
- The existing locked `fpl_v1_1_model.xi_assignment.optimize_best_formation` is connected through `generate_current_xi`, but the gate requires current-season confirmed tactical role evidence, fresh `locked_mm_pm_vfinal` P(start), matching official next GW, 11 legal distinct roles and sufficiently high evidence. The source 2026/27 did not provide lineups as of this date; **the present release therefore correctly has no claimed current tactical XI**.

## Verified integration and source quality
GitHub Actions real Publisher proof: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/37948736045
- 760 historical team lineups, 374 current identities with historical q, 322 with same-club historical H.
- Zero certified current XI on present inputs. Both data and app must label these as historical priors, not current known tactical facts.
- Model and CI tests: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/37949008268
- All code/HTML/data incorporated in the existing one-click publisher route; install/reopen app after using publisher.

## Blocker
To populate *current* 2026/27 role q/H and confidently publish XI, acquire completed match tactical lineups/formation/minutes from an attributable 2026/27 provider. The public current FPL-Core-Insights league CSV has playermatchstats and fixtures but no 2026/27 `lineups.csv`; FotMob API matchDetails for a sampled current-season match returned 404 from GitHub Actions. The official FPL bootstrap contains FPL position only, not detailed 21-role tactical slots. Do not infer these from FPL DEF/MID/FWD or use post-deadline data. Current historical q/H priors are an intermediate, honest input to a future genuinely live MM pipeline.
