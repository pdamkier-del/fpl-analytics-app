# 2026/27 live certification progress — frozen MM feature evidence (2026-10-10)

**State: NOT CERTIFIED. Do not activate locked_model_active.**

Repository branch: free-github-static-20261010. Continue from this branch's
current HEAD, not an older replay checkpoint. Frozen mathematics and locked
config are unchanged.

## Successful genuine current-season runs

The checksum-verified Work input checkpoint is restored by
scripts/restore_live_input_checkpoint.py --out .

The strict automated runner .github/workflows/live-mm-feature-readiness.yml
uses the actual historical builders on the restored input, then audits schema
and provenance. The completed six-GW test
[GitHub Actions 38038218669](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38038218669)
generated:

| Item | Verified count |
| --- | ---: |
| 2026/27 live target player-fixture rows, GW6–11 | 4,002 |
| Unique current players | 667 |
| Past FPL player-fixture results used for sequence | 3,202 |
| Frozen sequence columns computed | 20 |
| Observed provider player-event rows | 2,786 |
| Usable positive-minute FotMob provider records | 2,158 |
| Frozen performance columns computed | 28 |
| Target rows with positive observed performance history | 2,838 |
| Target outcomes read from GW6–11 | 0 |

The two builders and their strict reading of source history are:

- scripts/build_locked_live_sequence_features.py — calls the existing
  run_v4_three_state_sequence_experiment.add_sequence_features, including
  identical feature names and half-life/sequence calculations. Future target
  outcome placeholders are excluded from every cutoff and removed from output.
- scripts/build_locked_live_performance_features.py — calls the existing
  run_v4_performance_rating_experiment.add_features. Historical zero rules and
  frozen rating proxy stay unchanged. Explicit mapped source aliases handle
  FotMob 2026 keys expected_goals→xg, expected_assists→xa,
  ShotsOnTarget→shots_on_target, dribbles_succeeded→successful_dribbles,
  shot_blocks→blocks, without revising feature formula.

Sample observed provider coverage in latest success: xg 1089, xa 1533,
shots-on-target 1089. **tackles_won and accurate_passes_percent are not yet
certified against 2026 provider semantics**, even though the old model's
zero-default can produce numerically complete columns. Treat this as a
quality blocker; never relabel it verified without sourcing compatible data.

## Exact remaining minute-model blockers

The current strict feature readiness checker
scripts/audit_live_inference_readiness.py reports missing:

1. **base_logit** — original v2 baseline P(start) must be generated for
   the current cutoff using the original baseline architecture. Never replace
   it with FPL's ep_next, arbitrary start rates or 2025 static player forecasts.
2. **start_minutes_mean, cameo_minutes_mean,
   p_cameo_given_bench** — original conditional-duration and cameo
   priors must be recreated from verified pre-cutoff player minute histories,
   with explicit carryover/cold-start policy.
3. **7 XI relative/assignment features**:
   xi_assignment_score, xi_formation_score_gap, xi_hierarchy, xi_q_role,
   xi_role_competitors, xi_score_margin and xi_selected_map.
   Compute these only after real original P(start) and complete role history
   inference, using the locked XI assignment and relative competition code.
4. **Provider consistency** — current raw FotMob keys for tackles and
   passing are not one-to-one confirmed with training semantics. Avoid
   unexamined zero-fill and certify verified aliases/data first.

The original strict official Team News nullable chance is now correctly
accepted in the audit: official nulls are normal for available players,
and are not a reason to fail. Hard OUT/SUSPENDED release handling has been
**approved and integrated** into scripts/export_mm_release.py and
src/fpl_v1_1_model/live_availability_boundary.py. It writes both frozen raw
MM prediction and gated current-GW live minutes with sourced provenance.
Its verification is mandatory in scripts/publish_final_model.py.

## Required path to *actual* certification

1. Restore exact sources and construct original v2 baseline, conditional
   minute priors and XI features for ONE live origin GW, without future
   outcomes. Pass current strict feature readiness gate with real data.
2. Run the exact historical locked MM architecture and fixed parameters
   on the current GW. Generate genuine p_start, q_sub, sub_minutes and
   raw xmins; check exact-11, identity coverage, temporal cutoffs.
   Apply the approved hard ineligibility release boundary with source-scoped
   Team News; export mm_forecasts.csv.gz and the signed policy sidecar.
3. Feed that output into unchanged PM/vFinal simulator with all original
   xG/assist/keeper/BPS/DefCon/penalty/negative event components, all original
   as-of team strength inputs and Monte Carlo settings. Validate point output.
4. Execute the original TS v3 and all locked FH/WC/BB/TC strategies, using
   real squad/state inputs and genuine six-GW PM forecasts, not replay
   realizations. Check decision consistency and no post-cutoff information.
5. Re-run a real one-GW to six-GW chain with seeded reproducible artifacts,
   compare models/fixture/player/GW IDs and timestamps, source checksums,
   produce authentic component manifests, and only then allow
   locked_model_active=true.

**Do not treat passing web deployment, source extraction, 20/28 feature
calculations, or the existence of the final release gate as evidence the
whole final model ran.** Nothing currently warrants asserting that MM,
PM/vFinal, TS v3 and the chip coordinator ran end to end for 2026/27.
