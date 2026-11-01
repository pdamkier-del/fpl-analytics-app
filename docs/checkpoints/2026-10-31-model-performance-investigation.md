# Completed read-only model performance investigation

Existing experiment branch only. No production/app/model activation. Research implementation: `analysis/research_attack_budget.py`. Results and interpretation: `analysis/results/attack-budget-calibrated-20261031/README.md`; raw sensitivities under sibling `attack-budget-ablation-20261031`.

Completed 341 two-season historical fixture comparisons, 1,091 distinct players, 27,092 player-fixture rows per arm. Fixed current, raw individual, raw 50/50, smoothed common assists, FPL-assist-calibrated individual and calibrated 50/50; 400 draws each, same physical MM kernel, separate penalties, joint points and bonus. Fixed raw and calibrated blend/individual variants worsen overall and played xP RMSE in both seasons. Keep current model. Neither reused cohort nor named-player examples establish independent predictive superiority.

81 physical/role/unified-chain/snapshot regressions pass; preceding transfer audit 31 pass. New research simulator probability lookup is an in-memory AST copy with exact unmodified-parameter result identity checks, not an edited production engine. Calibration high-xP subgroup contains only155 observations; investigate goals/bonus and winner-selection uncertainty, not blanket assist reduction. Its second-season bias interval includes zero.

Correct earlier chat assumptions: JP injury already correctly gated to0; Jackson66.5xM includes non-start risk; FPL assists and xA differ; Barry has substantial historical xG. Verified current input scope still declares PL-only explicit workload and unimplemented structured coach statements, though starter-role history includes other competitions. Private manager inputs/results remain outside Git.
