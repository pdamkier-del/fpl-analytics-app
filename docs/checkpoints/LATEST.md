# Latest checkpoint: MM architecture frozen (2026-10-06)

See `2026-10-06-mm-final-architecture.md`.

The Minute Model (MM) is now structurally frozen as the agreed model, while
production promotion remains false pending genuinely fresh independent
validation. Locked architecture: exact-11 P(start), official-club workload,
verified non-PL q/H role history, Match Importance applied primarily to
historical hierarchy H using dynamic Competition Value + Stage + Opponent
Strength, q MI scale 0.10, H MI scale 0.40, evidence floor 0.35, retained
performance residual, league-state subappearance sequence, frozen starter
duration and 50/50 sequence-aware substitute duration blend (Ridge alpha 80).

Verified role-history coverage includes PL, Champions League, Europa League,
EFL Cup and the strictly verified subset of recovered FA Cup. Conference
League remains in workload history but is not assigned guessed roles when the
11-slot role evidence is insufficient. A tested all-official-match sequence
variant and a targeted uncertain-starter correction were both rejected because
they failed the development/generalisation guardrails.

Reused GW22-38 diagnostic versus the previous combined MM: state log-loss
0.437711 -> 0.435540, Brier 0.232550 -> 0.231644, xMins RMSE
21.465868 -> 21.446396, bias -0.222459 -> -0.164589; MAE worsens
11.444301 -> 11.549921. RMSE remains the primary conditional-mean xMins
objective and MAE is retained as an explicit guardrail.

**Next model area is PM. Do not tune MM indirectly during PM or TS work.**

---

# Latest checkpoint: combined exploratory minute candidate

See `2026-10-05-combined-minutes-candidate.md`. The current best exploratory
minute candidate combines v4 + last-match performance for P(start), a
sequence-aware P(sub|not start), unchanged v4 starter duration, and a 50/50
blend of v4 and sequence-aware substitute duration. On development GW16-21 it
improves both xMins MAE (11.413828 -> 11.395086) and RMSE
(21.734810 -> 21.670702). On the reused GW22-38 diagnostic it improves MAE
11.473765 -> 11.444301 and RMSE 21.583163 -> 21.465868 while also improving
start/state/sub probability metrics. This is saved, not promoted; independent
season/time validation is still required.

Next work moves to remaining xP components rather than continued broad minute
tuning. Priority weaknesses from the existing component audit: keeper saves,
DefCon calibration, negative-event penalties, and season-correct BPS/bonus.
Goal/assist role priors improve conditional component error but did not improve
joint point MAE; clean sheets and goals-conceded are aggregate-close.

# Latest checkpoint: completed role-event simulation

See `2026-10-05-role-event-integration.md`. Role event layer implemented and
tested, not promoted. 1,200-draw nonbonus MAE: current v4 0.828379 vs roles
0.829757. 144 fixtures / 11,794 rows; reused GW22–38, not full season/holdout.
218 integrity checks pass. Website explicitly deferred; no website changes.
Current v4 retained. Full-season data and season-rule gates remain below.

## Previous checkpoint: minute component experiment and Saturday target

See `2026-10-05-minutes-components-and-release-plan.md`. The user has
authorized preparing the complete model, with minutes first and detailed
roles considered for other components, targeting Saturday 10 October.

Completed: exact signed minute-error decomposition; 27 frozen component
combinations selected using development GW16–21 RMSE; selected substitute-
duration hybrid tested through the original joint simulator on all 144 paired
fixtures. Original control predictions are exactly unchanged. 43 experiment
checks pass. No estimator refits or model/policy promotion.

The hybrid slightly improves minute RMSE but worsens minute MAE. Its paired
nonbonus point MAE is 0.834813 versus current v4 0.831744; point RMSE is
1.591309 versus 1.585767. With 80 draws these small stochastic differences
are not proof of inferiority; there is no demonstrated downstream gain.
Retain current v4 as reference.

Detailed role known for 3,121/3,168 actual starters in the paired cohort.
Roles already inform minutes. Event rates currently use broad-position
priors plus individual history. Next role experiment should add audited,
predeadline role information with shrinkage/fallback to xG/xA and DefCon
components, selected on development data before joint evaluation.

Full v4 season validation still has concrete gaps: 196 origin-target cells,
32 roster rows across 26 fixtures, early as-of states, competition coverage,
and separately controlled season-rule integration. The release plan records
these acceptance gates. GW22–38 remains reused diagnostic.

## Previous completed direct evaluation

See `2026-10-04-direct-minutes-v4.md`.

Exact shared point-diagnostic cohort: 144 fixtures / 11,794 player-fixture
rows, GW22–38, 26 whole fixtures excluded in both arms. Saved forecasts only;
no fitting, prediction regeneration, model or transfer/chip policy changes.

Original v2 → selected v4 workload_start:
- Minute MAE: 11.969695 → 11.509261 (3.85% reduction).
- Minute RMSE: 21.920483 → 21.573631.
- Start Brier: 0.077751 → 0.075779.
- Start log loss: 0.259617 → 0.246429.
- Ten-bin calibration ECE: 0.024988 → 0.007284.

Internal role-control is a separate comparator (minute MAE 11.847375),
not the unchanged v2 joint-simulator control. Direct minute metrics already
existed on the broader saved dataset; this report verifies the exact matched
cohort and corrects the prior overly strong conversational status claim.

Weaknesses: actual substitute minute MAE worsens 19.412683 → 20.640091;
forward start Brier worsens; larger role-information-change bands show small
MAE regressions. Much of the aggregate improvement comes from nonappearance.
All slices based on actual outcomes are posthoc descriptive, never features.

107 report integrity/metric/calibration/partition/policy checks pass;
target starts and minutes additionally match Historical Core exactly.
Existing full test suite: 125 passed. Full evaluated rows are checksum packed
in `analysis/results/direct-minutes-v4-diagnostic-v1/`.

GW22–38 remains reused diagnostic, not new holdout. No full v4 season-points
claim. Independent evaluation and incomplete competition histories remain.
The separately completed old-model season reproduction has 2,096 net points
but is irrelevant to the new minute-model comparison; its results remain intact.

The requested direct evaluation is complete. Do not change the model or policy
silently: new tuning requires a separately defined development experiment and
independent evaluation period.
