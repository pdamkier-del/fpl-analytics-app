# Frozen exploratory minute candidate: performance + sequence state + blended sub duration

Status: saved candidate only; not promoted to production because all development
choices are sequentially tuned and GW22-38 is a reused diagnostic, not an
independent holdout.

## Architecture

Expected minutes:

E[M] = P(start) * E[M|start] + (1-P(start)) * P(sub|not start) * E[M|sub]

Frozen exploratory components:
- P(start): v4 plus last-match performance residual correction, L2=0.5.
- P(sub|not start): sequence-aware binary model, C=4, blended 75% on logit scale
  with the inherited v4 conditional-sub probability.
- E[M|start]: inherited v4 conditional starter duration, unchanged.
- E[M|sub]: 50/50 blend of inherited v4 cameo duration and the sequence-aware
  sub-duration Ridge model, alpha=80.

The last-match performance layer uses only historical match-stat ingredients
known before the forecast cutoff. No provider match-rating field exists in the
frozen source; the experiment uses a rating-like proxy from goals, assists,
xG/xA, shots on target, chances, dribbles, defensive actions, passing, saves,
goals prevented, goals conceded and dispossessions.

## Development selection (GW16-21)

Baseline v4:
- start Brier 0.075578
- start log loss 0.247174
- state Brier 0.241097
- state log loss 0.620066
- sub Brier given non-start 0.088855
- xMins MAE 11.413828
- xMins RMSE 21.734810

Selected combined candidate:
- start Brier 0.075333
- start log loss 0.246858
- state Brier 0.235059
- state log loss 0.453543
- sub Brier given non-start 0.081592
- xMins MAE 11.395086
- xMins RMSE 21.670702

## Reused GW22-38 diagnostic

Baseline v4:
- start Brier 0.075063
- start log loss 0.244381
- state Brier 0.239032
- state log loss 0.571050
- sub Brier given non-start 0.086339
- xMins MAE 11.473765
- xMins RMSE 21.583163

Combined candidate:
- start Brier 0.074700
- start log loss 0.243136
- state Brier 0.232550
- state log loss 0.437711
- sub Brier given non-start 0.078934
- xMins MAE 11.444301
- xMins RMSE 21.465868

Diagnostic deltas candidate minus v4:
- xMins MAE -0.029464 minutes
- xMins RMSE -0.117295 minutes
- start log loss -0.001245
- state log loss -0.133338

The combined candidate improves all central metrics in the reused diagnostic,
but this is not independent evidence and must not be described as a promoted
or production-proven model.

## Interpretation

The main remaining minute errors are concentrated in player-state transitions.
Sequence-aware state information is much more useful for substitute-vs-zero
classification than replacing the already strong v4 starter-duration model.
Recent match performance adds a small but consistent residual signal to
P(start). A partial rather than full replacement of substitute duration gives
the best MAE/RMSE compromise.

## Frozen artifacts

Primary result:
- analysis/results/v4-combined-minutes-20261005-v1/

Supporting experiments:
- analysis/results/v4-performance-rating-20261005-v1/
- analysis/results/v4-three-state-sequence-20261005-v1/
- analysis/results/v4-three-state-duration-20261005-v1/
- analysis/results/v4-three-state-20261005-v1/
- analysis/results/v4rc-20261005-v1/

Scripts and manifests in those folders provide reproducibility and source
checksums.

## Next model work

Stop broad minute tuning here. Preserve this candidate while working on the
remaining xP components. Highest-priority known component weaknesses from the
current joint audit are keeper save points, DefCon calibration, negative-event
penalties and season-correct BPS/bonus. Goal and assist priors are already
reasonable but mildly high in aggregate; detailed role priors improve their
conditional component error yet did not improve joint point MAE. Clean-sheet
and goals-conceded components are aggregate-close and lower priority.

Independent time/season validation remains mandatory before freezing this
minute candidate into the final production model.
