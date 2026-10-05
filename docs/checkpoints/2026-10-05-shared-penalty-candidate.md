# Shared penalty model candidate

A single shared penalty process is now implemented in the joint simulator.

Architecture:
1. Team penalty occurrence blends the team's own prior penalty-award rate and
   the opponent's prior penalty-conceded rate, both shrunk toward league average.
2. Penalty taker allocation uses recency-weighted prior attempts within team.
3. Taker conversion is shrunk toward league conversion.
4. A miss is one shared event: taker receives -2, and if saved the active
   opposing goalkeeper receives +5.
5. Explicit penalty saves also enter the goalkeeper save count.
6. Expected penalty-save mass is removed from the ordinary save Poisson.
7. Expected scored-penalty mass is removed from the ordinary team-goal Poisson
   before explicit scored penalties are simulated, so total expected team goals
   are not inflated.

Selected exploratory parameters:
- occurrence EB tau: 20 team fixtures
- taker half-life: 6 GWs
- conversion tau: 20 attempts
- P(GK save | penalty miss): 0.7333 from 11 saves / 15 misses in the available
  2025/26 FPL merged data; this is a small sample and must be treated cautiously.

Occurrence diagnostics:
- GW6-21 actual team-side penalty-event rate 0.1156, predicted 0.1186
- reused GW22-38 actual 0.1088, predicted 0.1202

Taker diagnostic:
- mean probability assigned to the eventual taker ~0.72 on reused GW22-38.
Primary-taker hit rate is much lower (~0.32), which confirms that keeping a
probability distribution over takers is preferable to a hard first-taker label.

Conversion:
- development actual 0.796, predicted 0.780
- reused diagnostic actual 0.895, predicted 0.866

Reused GW22-38 joint diagnostic, marginally on top of final DC:
- final DC baseline: MAE 0.822654, RMSE 1.576299, bias +0.031103
- + shared penalties: MAE 0.819678, RMSE 1.574534, bias +0.024530
- delta MAE -0.002976
- delta RMSE -0.001765
- delta bias -0.006573

This is a useful downstream improvement, but GW22-38 is reused diagnostic data,
not an independent holdout. The penalty-save conditional probability is especially
sample-limited. Keep this as the current penalty candidate, not production truth.

Artifacts:
analysis/results/shared-penalty-model-20261005-v1/
analysis/results/shared-penalty-joint-20261005-v1/
