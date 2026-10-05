# Minute components and target: Saturday 10 October 2026

Continues verified branch HEAD `29765a3794d698131b174e62be0a947d1d9ad921`.
User authorizes preparing the complete model, prioritizing minutes, testing
the whole pipeline, and investigating use of detailed positions/roles for
other event components. Saturday is the target date, not a claim that data
gaps have already been resolved or work runs unattended between turns.

## Completed in this checkpoint

Tested the fixed 27 combinations of existing base/role/workload conditional
start duration, substitute probability and substitute duration. P(start)
stayed at frozen v4. Selected lowest RMSE on GW16–21 only; selection saved
before reading GW22–38 outcomes. No estimator refit. The selected combination
replaces only substitute duration with the workload model. This is an
exploratory composition screen on an already-used development period.

| Metric | Existing v4 | Development-selected hybrid |
| --- | ---: | ---: |
| Development minute RMSE | 21.734810 | 21.691972 |
| Development minute MAE | 11.413821 | 11.549020 |
| Reused 144-fixture minute RMSE | 21.573631 | 21.526306 |
| Reused minute MAE | 11.509261 | 11.611091 |
| Paired joint nonbonus point MAE | 0.831744 | 0.834813 |
| Paired joint nonbonus point RMSE | 1.585767 | 1.591309 |

The original joint adapter/simulator ran all 144 fixtures / 11,794 rows,
80 draws per fixture/arm, original seed base 26092501. Control predictions
are exactly identical to the previous run; candidate component forecasts
are the only changed inputs. Point targets are read after predictions are
saved. 43 source/hash/control/accounting checks pass. Existing policy hashes
are unchanged. Small stochastic point differences are not proof that the
hybrid is inferior; there is no demonstrated downstream improvement at this
budget, so no production model promotion is made.

Error identity, with y=start, z=sub appearance among nonstarters:

`predicted-actual = (p-y)*(S-q*C) + y*(S-M) + (1-y)*(q-z)*C + (1-y)*z*(C-M)`.

The identity reconstructs every row. For actual substitutes, mean signed
terms are +20.267 (start selection), −8.535 (sub appearance), −0.008 (sub
duration), totaling +11.724 minutes. These terms cancel and are descriptive,
not causal effects or an additive decomposition of MAE. Conditional substitute
duration MAE does improve from 13.566 to 10.954 with the workload model, but
this does not imply improved unconditional expected minutes or points.

## Roles: what is already present

`minutes_decomposition.component_inputs` includes broad position and expected
detailed role, role/hierarchy history and workload in the workload variant.
`deadline_components.player_components_at_deadline` uses broad FPL-position
priors for xG/xA, DefCon and cards plus player history. It does not consume
the detailed role distribution in these event priors.

In the paired cohort, 3,121/3,168 actual starters have a known predeadline
expected role. UNKNOWN covers 5,342/11,794 roster rows overall, concentrated
among nonstarters. Do not equate overall unknown rate with starter coverage,
or treat retrospective target roles as available features.

## Delivery gates for the Saturday target

1. **Minutes:** retain frozen v4 reference; diagnose start-versus-substitute
   ambiguity using known-before-deadline inputs. Fix a small development-only
   candidate set and preserve development selection. Evaluate start Brier/
   log loss, minute RMSE/MAE, appearance calibration and per-position slices.
2. **Detailed roles in event rates:** audit time-stamped role state per
   historical observation; test separate role-informed xG/xA and DefCon
   priors with shrinkage toward broad position/player history. Keep fallback
   for UNKNOWN and sparse roles. Do not fit 20 unrelated small-sample models
   or replace FPL scoring positions with tactical roles. Select component
   changes on development data, then run the joint point comparison.
3. **Complete point pipeline:** align the scoring profile with the replay
   season in a separate controlled experiment; retain the existing BPS audit
   limitations until verified. Validate minutes → on-pitch events → FPL
   points, captain/autosubs, and uncertainty. Increase stochastic precision
   only for a fixed finalist comparison; do not tune repeatedly on GW22–38.
4. **Decision/release readiness:** use the audited season rules without
   retuning transfer/chip strategy in the same comparison. Verify roster,
   prices, fixture schedules and forecast horizon at each deadline. Save
   source/configuration hashes, reproducible reports and rollback reference.

Concrete unresolved gaps: 26 whole fixtures/32 player rows lack verified
predeadline roster evidence; selected v4 full-season coverage still lacks
196 origin-target horizon cells; early as-of prices/schedules and complete
official-competition histories remain incomplete. The completed legacy season
run does not close these v4 gaps. A claim of complete full-season v4 validation
cannot pass until they are resolved or an explicitly bounded scope is agreed.

GW22–38 stays reused diagnostic. An independent evaluation period still
needs to be identified without reusing outcomes already inspected. A new
independent result cannot be manufactured by relabelling these rows.

Artifacts: `minutes-components-20261005-v1`,
`minutes-hybrid-inputs-20261005-v1`, `minutes-hybrid-paired-20261005-v1`
under `analysis/results/`. Existing v4, original sources, scoring, transfer
policy, chip strategy and previous results are preserved.
