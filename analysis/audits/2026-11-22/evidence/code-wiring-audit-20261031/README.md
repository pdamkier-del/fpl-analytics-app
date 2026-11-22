# Current code/input wiring audit — defects and missing connections

This is a source-to-output correctness audit, not an alternative-model accuracy screen. All input hashes were checked against published forecast seal `80905646f26560ac37fe6af8ca6d7d509287ecbf0d6a9c34217332fdba41238c` (31 October capture). It does not describe unknown subsequent live snapshots. No production/model/app change or official FPL action was made.

## High priority: persistent unavailability is dropped after the origin GW

`scripts/build_current_b_inputs.py:128–132` restricts eligible news and medical-out state to the origin GW; future rows get UNKNOWN. The existing horizon helper `scripts/gk_solo_role.py:151–156` handles only season-long goalkeeper loans. This does not cover outfield season loans or permanent departures for any position.

Verified current output: **85 players** with official status `u` and explicit permanent-departure (34) or rest-of-season-loan (51) text receive positive future minutes: 83 outfield and 2 goalkeepers. Examples include Beto, Millar and Drameh. Full exact public player/fixture evidence is in `findings.json`. These players are not verified future competitors; their minutes also consume team start/minute mass. Correct 900/90 totals do not establish correct eligibility.

## High priority: all-competition workload is not wired into the B minute features

Current source observations start from the FPL PL table in `scripts/build_current_b_inputs.py:40–45`; the match identity lookup explicitly selects `tournament=='prem'` at line50. Those observations feed `prior_features` and its `rest_days`, `minutes_7d` and `minutes_14d` in `scripts/current_b_features.py:60–63`.

Verified Cherki example: the hashed tactical role ledger contains a PL start with45 minutes on24 October plus an EFL start with90 minutes on28 October, both known before the forecast cutoff. The workload target contains **45 minutes in7days**, not at least135, and rest approximately6.89days instead of approximately2.56days since the later sourced match. Thus the extra match is captured and used in tactical role history, but absent from the explicit workload branch. This is an integration gap, not proof that a particular higher/lower xP is correct. Historical training contracts must be kept consistent when fixing the connection.

## Medium priority: known return-date text is not modeled across the horizon

`medical_fields` in `scripts/experimental_role_injury_mm.py:13–19` preserves an absence string but always returns `return_earliest=None` and `return_latest=None`. Future news gating then removes the current injury information. Verified example: Sávio's frozen official news says expected back21November, while the forecast gives27.6minutes in GW10 on7November. An estimated return date is not an absolute medical guarantee; the confirmed gap is that the date is not an input to a horizon-specific availability estimate.

## Medium priority: upcoming relative match importance is explicitly neutral

`scripts/joint_role_bridge.py:58–60` computes importance using known PL stage/current month and active competitions but explicitly leaves opponent/relative upcoming priority neutral. `forecast.role_assignment.future_priority` confirms this. Past CL participation can affect hierarchy; it does not establish a forward-looking inference that a player will be rested before an upcoming CL match. This is missing agreed context, not a newly discovered arithmetic bug.

## Other reviewed boundaries

- Structured coach statements are explicitly unimplemented in the hashed provenance.
- PM uses a shared fixture contract and overrides season BPS rules before its final simulation. Ordinary and penalty goals remain separate; point components reconcile and MM/PM share the physical kernel.
- The B XI chooser selects a legal XI using summed marginal xP before jointly scoring autosubs and captain fallback (`scripts/b_preview_ts.py:65–86`). It does not globally optimize all XI/bench policies under the final joint score.
- Ordinary TS candidate generation excludes a negative individual-value transfer leg (`src/fpl_xpts/transfer_planner.py:282–286`) even when it can finance a better bundle, and restricts the candidate pool. These are documented search limitations; no current manager's globally optimal alternative has been proven by this audit.
- Cash, sale prices, FT/hits and WC comparison were independently checked in the earlier private transfer audit; passing those checks does not test the missing workload/availability connections above.
- No newly fetched data, inferred injuries, invented coach quotes, parameter changes or player-specific patches were used.

## Reproduce

Run `analysis/audit_current_feature_wiring.py` through the locked numerical runtime with the retained public forecast and the matching `work/current-B-inputs` from GitHub artifact13037202812. The helper checks every sealed input checksum and reports source-to-output violations; it does not pretend those violations are passing model tests. Inputs contain public football facts, not manager state. Additional actual missing workload can exceed the starter-only evidence shown here.
