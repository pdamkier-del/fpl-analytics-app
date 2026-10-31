# PM event conservation: independent source-code review (31 October 2026)

Scope: read-only review of current `experiment-goalkeeper-coverage-20261018` at branching time. No changes to locked production, B preview, PM distributions, scoring rules, or TS. No historical magnitude or current-player effect is claimed until a full runtime replay.

## Confirmed code-control-flow defect to reproduce

- `src/fpl_v1_1_model/joint_simulator.py:84-88` `_weighted_choice` returns `None` when all effective weights are zero or the active player set is empty.
- In the goal-event allocation loop `joint_simulator.py:276-285`, a non-penalty team goal gets a `scorer=None` if positive goal lambda meets a zero-active-weight event. It still lives in `goal_events`.
- The assist block is reached whenever `not is_pen`, regardless of whether a scorer was selected; with a second active player having `assist_weight>0`, an assist can be assigned to an event with no selected scorer. Thus there is **no invariant** `awarded_fpl_assists <= attributed_goals` in this current implementation.
- In `joint_simulator.py:287-294`, opposing goals conceded and CS evaluate all `goal_events` independent of successful scorer attribution. Team goal budget is not directly inflated by this; player event accounting can be inconsistent. A scorer-less event can represent an own goal or unlisted player, but there is no explicit type assigned here, so do **not** naively discard it or award it to a random listed player.

### Minimal deterministic contract case

Construct MatchSimInput: one active home player with goal_weight=0, assist_weight=1, at least one active opposing player (proper GK if necessary), lambda_home_goals>0; no penalties; assist_probability_per_goal=1; fixed explicit timeline with home player on pitch for whole fixture if needed.

Force or seed exactly one home ordinary-goal event at a time home player is active. Expected under current flow:
- `scorer is None`
- Home player `goals == 0`, `assists == 1`.
- Away goals-conceded counts the goal.

That is a deterministic counterexample to an event attribution invariant; its **frequency in real forecasts is currently unmeasured**.

Note: `goal_weight=0` is possible for an active player with `goal_mu<=0` or `expected_minutes<=0` (`phase4b._rate_weight`), even if the active interval comes from another minute distribution. The actual PM input pipeline may make this very rare. Measure before severity escalation.

## Other important but not yet established as defects

1. `run_live_vfinal_team_latent.py` calls `fit_team_latent` with historically observed **xG** as dependent variable; no independently fitted actual-goals finishing residual is visible. Check out-of-time lambda calibration against actual G and xG; do not force goals lower from intuition.
2. `run_vfinal_integrated.py:normalized_mu` divides each player's `rate * control_xmins/90` by team sum and multiples by goal lambda; `phase4b._rate_weight` then converts `goal_mu / expected_minutes` to an on-pitch weight, and simulator re-normalizes among active players. Verify how preview B vs control xM alters the intended pre-match individual shares, especially role/absence changes; do not claim guaranteed inflation from normalization alone.
3. `phase4b.build_match_input` has default `assist_probability_per_goal=.90`, though live fixture may supply its own value. Audit vs official **FPL** assists, not Opta-only assists, and score special cases separately.
4. `joint_simulator.py` reserves scored-penalty mean via `h_open=max(0,team_lambda-expected_penalty_goals)`. Confirm team-level conversion assumptions vs individual kicker conversion, nonpenalty goal mean, and future injury/penalty hierarchy (the actual sampler must be audited).
5. 400 Monte Carlo draws per match can produce material rare-event noise. Check repeated-seed variation and objective confidence intervals before changing xP to address small deviations.

## Requested acceptance tests for Codex (separate implementation branch)
- Record goal event category (ordinary attributed/own-goal/unlisted/penalty); ensure score, concessions, assists, and points reconcile with **documented** FPL rules.
- Test no FPL assist on an unattributed scorer when it lacks a permissible special-case event.
- Test positive lambda and zero scorer weight; empty and partial roster; one vs multi scorers; goal after substitution; missing team keeper; penalty taker converted vs missed.
- Replay current 6GW and historical sources and report: unattributed events per 10,000 team goals, assists with no assigned scorer, source-specific false attribution, xP changes by position and component, and calibration.
- No performance claim without sealed cutoff and out-of-time labels. No preview production switch without green regression suite.

## Next steps / ownership
Independent audit may update this file but **must not modify** `joint_simulator.py` or B/PM live feature files while Codex handles Issue #24. Codex owns implementation after MM data repairs. Related issues: #24, #25, #26, #27, #28.
