# Cherki: current minute risk and press-conference evidence

Read-only review, 23 October 2026. Existing PR #22 branch. No numerical B,
production, deployment or private manager-state changes. Machine-readable
checks: `analysis/results/cherki-coach-context-20261023/diagnostic.json`.

## Verified current forecast

The served forecast is `352349728ebaf2ddfe5356987c3d65ad291b630071e257406039d911ea513383`,
source `b0a229c0de05a640f49937616c070dfbcdf986fc`, data as of 23 October
12:59:55 UTC / 14:59:55 Copenhagen. Current role/PM inputs were obtained from
the successful exact-source CI run 39955376460, rather than reconstructed from
an older snapshot.

Cherki's GW8 forecast is P(start) **48.0137%**, xM = analytical PM minutes
**46.2264**, P(60+) **48.0109%**, P(90) **38.6030%**, xP **2.735**.
P(no appearance) is **33.9439%**. His role remains
`rotation_or_short_history`; his historical primary tactical role is CAM.
Minute mixture and all point components reconcile. His mean score among the
167 draws with exactly 90 minutes is 4.6886. This conditional sample is not a
guaranteed-90 counterfactual or a proposed replacement xP.

The same-source ordinary-goal/penalty intervention changes xP only
**2.820 → 2.735**, leaving every analytical minute probability unchanged.
The current forecast's Monte Carlo standard error is approximately 0.169
points; this individual draw-dependent difference is not an established
change in predictive quality. Minute/start risk is the main reason for his
low aggregate xP, not a penalty-taker downgrade.

## Actual CL information and partial consumption

Fresh FotMob match 6106257 confirms 90 minutes, one goal, five shots, three
chances created, xG **0.34**, native npxG **0.34**, xA **0.42** versus AEK
on 20 October. The official club article also confirms the goal.

The archived live input's classified role ledger contains that CL appearance:
CAM, 90 minutes, known-at 20 October 23:00 UTC, before the forecast cutoff.
It therefore supplies the existing all-competition joint-role history.
The PM performance fields have `perf_last_xgi=0.76` and
`perf_last_goal_assist=1`; the good CL game has not vanished from the entire
pipeline.

Integration remains partial:

- B's explicit PR9 workload/last-start features consume PL observations.
  They contain last-started=0, seven-day minutes=0, fourteen-day minutes=90,
  and rest=11.8898 days. Verified all-competition context at the same cutoff
  instead contains 90 minutes in seven days, 225 in fourteen, and 2.7439 days
  since the latest appearance. These fields are explicitly documented as
  PL-only in the current implementation. Other upstream/role mechanisms do
  consume cross-competition context; this is not proof the whole model treats
  Cherki as fully rested for twelve days.
- The newly separated ordinary-goal head uses previous **played PL** NP-xG
  features: last xG 0.58, recent-three 0.372857. It excludes the unused PL
  bench observation from attacking performance, but does not use the CL
  npxG 0.34 as its latest observation. The unchanged assist/performance and
  all-competition role channels are separate.
- The current pipeline does not extract structured coach quotes. The latest
  FPL Cherki record is available with an empty news field. That feed does not
  convey the coach's affirmative tactical role description.

PL and FotMob xG scales must not be silently spliced together. A future
cross-competition performance candidate needs verified NP events,
provider/competition/opponent handling and validation; a single goal is not
a justified finishing boost. Likewise, replacing PL-only workload with all
competitions requires consistent historical training features and labels.

## Exact official quote

[City's official article](https://www.mancity.com/news/mens/enzo-maresca-aston-villa-press-conference-rayan-cherki-63928260)
is dated **22 October 2026**, displaying 11:00 (page timezone unverified).
It was fetched on 23 October at 16:32:49 UTC / 18:32:49 Copenhagen; its source
hash and capture receipt are retained with the diagnostic.

Maresca calls Cherki “one of the best players in Europe when he is in the
right position.” He describes receiving between the lines, staying higher
rather than dropping too deep, and being important in that position.
The article reports six goals and two assists in eleven all-competition
appearances. This is affirmative, position-dependent quality/role evidence,
**not an explicit promise to start the next PL game**. It predates the
current forecast, but the current model has no structured consumption path.

## General integration design and required test

1. Capture official club press conferences/articles with source URL, original
   excerpt, stable speaker/player identity, publication timestamp or stated
   timestamp precision, actual first-observed timestamp, competition and
   fixture scope. Preserve the original and deduplicate syndicated/repeated
   quotes. A missing statement is unknown, not negative evidence.
2. Extract distinct categories: injury/availability, explicit start/rest or
   minutes restriction, longer-term hierarchy, tactical position, and generic
   praise. Store extraction confidence and any conditional wording. An LLM may
   classify sourced text; it must not invent a quote, probability or injury.
3. Feed these into MM's existing role/availability/selection machinery as
   separate evidence, with incremental influence learned against the frozen
   baseline. Coach/source reliability and temporal decay require shrinkage.
   Generic praise must not receive the weight of an explicit start statement.
   Keep the joint ten-outfield/one-GK constraints and hard availability caps.
   PM/TS receive those same resulting minutes and scenarios; there is no
   independent press-conference xP multiplier. An attacking-position effect
   on event rates is a separately tested role mechanism.
4. Test all covered players/clubs prospectively or with timestamp-verified
   historical captures, keeping source availability strictly before forecast
   origin. Extractor correctness needs audited labels; forecasting needs
   time-separated start Brier/log loss, minute MAE/bias, P(0)/P(60+)/P(90)
   calibration and xP MAE/bias, including rotation and contradictory-quote
   subgroups. Compare quote-only, consistent all-competition workload-only,
   and combined candidates to distinguish effects and double counting.
   Check exact MM→PM→TS consistency and default-production parity.

The preceding European residual experiment was not activated because its
intended role-recovery subgroup worsened and later-season coverage was sparse.
It does not validate this new quote-based mechanism, nor demonstrate that
coach information is useless. No manually selected Cherki start probability
or untested live change is introduced by this review. Current evidence
establishes a plausible missing information channel, not the correct start
probability or a proved historical forecasting improvement.
