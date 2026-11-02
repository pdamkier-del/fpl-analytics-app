# FPL canonical data architecture — source of truth

Status: **opt-in refactor, production unchanged**. Scope is input ownership and lineage; it is not a new scoring model.

## One pipeline

1. **Raw observations** (append-only, timestamped): fixture results, xG, xA, goals, shots, defensive events, saves, injuries, suspensions, team news, formation and observed player positions. Data is tagged with `available_at` and `fixture_uuid`.
2. **Team snapshot** (one record per team per forecast cutoff): attack/defence strength, expected team goals for the exact opponent, goal-concession context, home/away, fixture congestion, penalty intensity. All club identities use `team_id`. Global estimation functions apply uniformly to every club.
3. **Role snapshot** (one player per team/fixture/cutoff): official FPL position, probabilistic tactical roles (`q_*`), availability evidence and the historically established slot/starter-role evidence. Role probabilities are determined before the target match; observed future lineup/coordinates cannot leak into forecast.
4. **Player snapshot** (one player per fixture/cutoff): historical xG/90, xA/90, minutes and disciplinary/defensive/goalkeeper rates; historical exposure and uncertainty. Priors share information by FPL position and optionally tactical role. **No target labels in the inputs.**
5. **Canonical matchup projection**: locked MM calculates start/cameo/minute distribution; locked team/attack components normalize individual goals and assists to team totals; PM adapter calculates remaining event inputs.
6. **Frozen PM -> TS v3**: unchanged scoring, sampling and strategy, six-GW forecast.

## Data ownership rules

| Owner | Primary keys | Owns | Does not own |
|---|---|---|---|
| Fixture | fixture_uuid, cutoff | Home/away teams; kickoff/deadline; team-goal expectations for this matchup | Player history |
| Team | fixture_uuid, team_id, cutoff | Club-specific per-fixture penalty/context fields; team trends (upstream) | Duplicate fixture-level lambdas |
| Role | fixture_uuid, player_uuid, cutoff | Tactical role probabilities, role provenance, pre-deadline lineup hypotheses | Observed target-game formation |
| Player | fixture_uuid, player_uuid, cutoff | Official FPL position, player rates, availability, MM components | Opponent team strength |
| Derived PM | same player and fixture keys | goal_mu, assist_mu, mu_dc, bps_background_rate90 etc. | Independent estimates of the same team goals |

An auditable subset of these rules lives in `src/fpl_v1_1_model/feature_registry.py`. The full raw/derived feature inventory must be extended as each upstream builder is migrated; the registry is **not** a complete list of every historical feature yet.

## What is actually simplified

- Repeat `control_*` and `v4_*` input aliases only at the locked simulator boundary **when identical**. Genuine alternative scenarios remain distinct.
- Preserve one estimator per statistical target. xG and observed goals are not independent targets to add together; observed goals may help calibrate finishing.
- Estimate a player's xG/90, xA/90, DC and minutes with uncertainty using historical exposure and position/role priors; avoid hard-coded club or player overrides.
- Maintain DefCon and BPS *distribution* parameters where evidence shows their variance matters to FPL thresholds.
- Keep FPL rules, rarer events and scoring mechanics explicitly in PM; do not replace them by a correlated aggregate.

## Three gates before any live migration

**Schema gate:** unique keys; two teams per fixture; timezone-aware cutoff; no feature name with conflicting owners; no missing rates silently filled with zero; role distribution sums to 1 or is explicitly unknown.

**Parity gate:** run the identical fixture through the old and canonical adapter; compare serialized MatchSimInput and seeded simulation predictions including components and total xP. Must have identical model inputs before asserting equivalence. Holdout ratings and lineup inputs must remain deadline-correct.

**Value gate:** any reduction in the *statistical estimation* of active features is a separate A/B experiment; compare out-of-sample PM xP/MAE, RMSE, likelihood, calibration and component-specific FPL threshold errors. No auto-merge on correlations alone.

## Work sequence

A. Define ownership registry and documentation (this branch).
B. Add schema tests against real live and historical rows; instrument observed lineage and missing-field counts.
C. Route one actual fixture through canonical tables and prove model-input parity, then 1 GW, then 6 GWs.
D. Only once parity is established, migrate live data producers. Keep the existing production branch untouched until CI and historical regression gates succeed.
E. Run feature-ablation research independently and promote only evidenced changes.

## Existing code to reuse

- `fixture_input.py`: typed player/team/match split and validation.
- `role_classifier.py` and `role_event_priors.py`: pre-deadline structural roles and soft role priors.
- `attack.py`: shrunk rates, propensities, normalization to team event totals.
- `canonical_fixture_input.py`: optional canonical minute aliases.
- `joint_simulator.py`: locked event and FPL scoring logic.

Avoid adding a new parallel simulator or bypassing the frozen MM/PM boundary.
